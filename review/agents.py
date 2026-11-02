"""Six isolated, tool-using review contexts sharing only model weights. No remote inference.

The only tool actions are selecting a public source excerpt from an in-memory allowlist
and searching an installed copy of the public coverage registry. Nothing the model writes
is executed. Reports are leads for independent checking, not professional opinions.
"""
import importlib.util
import json
import os
import re
from pathlib import Path

import torch
from huggingface_hub import HfApi
from transformers import AutoModelForCausalLM, AutoTokenizer

BASE = Path('src/uk_data_mcp')
MODEL = 'Qwen/Qwen2.5-Coder-1.5B-Instruct'
roles = {
    'general_user': ('First-time MCP user trying to find a service and recover from missing data.', 'civil_server.py', 'async def invoke', 'utilities'),
    'geotechnical': ('GI engineer selecting logs to review and checking whether the coordinates and positional uncertainty support a near-boundary decision.', 'corridor.py', 'def inspect_feature', 'boreholes'),
    'water': ('Water-utility engineer assessing a proposed sewer diversion: distinguish proximity to defences, local sewer capacity and company-wide leakage.', '_public_endpoints.py', 'async def company_leakage', 'sewer capacity'),
    'gas': ('Gas distribution asset-protection engineer looking for a gas main, plans and a safe handoff. Do not give excavation instructions.', '_civil_routes.py', "R('utilities'", 'gas main'),
    'electricity': ('Distribution planner assessing a 2 MW connection: distinguish indicative headroom, buried cable records and a connection offer.', '_civil_routes.py', "R('energy'", 'electricity grid'),
    'council_developer': ('Local planning authority and development applicant: distinguish a ward traversed from a beneficiary, and a point search from parcel-wide constraints.', 'corridor_schedule.py', 'def write_schedule', 'planning'),
}


def extract(name, key, width=2300):
    s = (BASE/name).read_text(encoding='utf-8')
    n = s.index(key)
    return f'{name}:{s[:n].count(chr(10))+1}\n'+s[n:n+width]


def run():
    rev = HfApi().model_info(MODEL, revision='main').sha
    if not re.fullmatch('[a-f0-9]{40}', rev) or not rev.startswith('2e1fd39'):
        raise RuntimeError('Unexpected model revision; review before running.')
    tok = AutoTokenizer.from_pretrained(MODEL, revision=rev, trust_remote_code=False)
    tok.padding_side = 'left'
    tok.pad_token = tok.eos_token
    torch.set_num_threads(min(4, os.cpu_count() or 1))
    model = AutoModelForCausalLM.from_pretrained(MODEL, revision=rev, dtype=torch.float32,
                                               use_safetensors=True, trust_remote_code=False).eval()

    def answers(chats, n):
        inputs = tok([tok.apply_chat_template(c, tokenize=False, add_generation_prompt=True) for c in chats], padding=True, return_tensors='pt')
        with torch.inference_mode():
            ids = model.generate(**inputs, max_new_tokens=n, do_sample=False, pad_token_id=tok.pad_token_id)
        return tok.batch_decode(ids[:, inputs['input_ids'].shape[1]:], skip_special_tokens=True)

    spec = importlib.util.spec_from_file_location('local_public_registry', BASE/'_civil_routes.py')
    routes = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(routes)
    cases = list(roles.items())
    chats = []
    for role,(task, name, key, query) in cases:
        chats.append([{'role':'system','content':'You are one independent software reviewer. Do not claim to represent an actual organisation. You cannot access other reviewers. Only the supplied public code and evidence are relevant.'},
                      {'role':'user','content':f'Role: {role}. Task: {task}\nPick one read-only tool: SOURCE to inspect relevant application code, or DIRECTORY to examine routing for {query!r}. Return a single tool name.'}])
    picks = answers(chats, 8)
    records = []
    for (role,(task, name, key, query)),chat,pick in zip(cases,chats,picks):
        selected = 'DIRECTORY' if 'DIRECTORY' in pick.upper() else 'SOURCE'
        evidence = extract(name,key)
        directory = routes.civil_coverage(query)
        extra = (json.dumps(directory,ensure_ascii=True)[:2700] if selected=='DIRECTORY' else extract(name,key,3200))
        chat.extend([{'role':'assistant','content':selected},{'role':'user','content':f'Tool result: {extra}\nSupporting source excerpt: {evidence[:1100]}\nGive one specific usability or correctness risk for your role and one falsifiable test or handoff. Name the code or source. No unverified claims of running tests. Maximum 90 words.'}])
        records.append({'role':role,'question':task,'selected_tool':selected,'raw_choice':pick,'excerpt':f'{name}::{key}','base_route_query':query,'base_route_hits':directory['count']})
    for record,text in zip(records, answers(chats,135)):
        record['model_review'] = text.strip()
        if not text.strip():
            raise ValueError('Empty agent completion')
        print('REVIEW '+json.dumps(record, ensure_ascii=True), flush=True)
    Path('role-reviews.json').write_text(json.dumps({'model':MODEL,'model_revision':rev,'source_revision':'c7debb9cb833f9b8fa81ef25f16f84ad1be8599f','reviews':records},indent=2))


if __name__=='__main__':
    run()
