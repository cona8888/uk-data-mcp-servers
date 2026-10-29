"""Coverage accounting shared by study assembly and validated exports."""


def incomplete_entries(evidence: list[dict]) -> list[dict]:
    incomplete = []
    for entry in evidence:
        result = entry["result"]
        if entry["status"] != "partial" and not (result.get("pagination") or {}).get("next_page"):
            continue
        if entry.get("pagination_followed") and entry.get("tool") == "bgs_features":
            arguments = entry["arguments"]
            continuation = (result.get("pagination") or {}).get("next_page") or {}
            next_offset = continuation.get("offset") if isinstance(continuation, dict) else None
            # A saved marker alone cannot prove that a page was actually followed.
            matches = [
                candidate for candidate in evidence
                if candidate is not entry and candidate.get("tool") == "bgs_features"
                and candidate["arguments"].get("offset", 0) == next_offset
                and all(candidate["arguments"].get(key) == arguments.get(key)
                        for key in ("collection", "bbox", "limit", "include_geometry"))
            ]
            if (isinstance(next_offset, int) and not isinstance(next_offset, bool)
                    and next_offset == arguments.get("offset", 0) + len(result.get("data", []))
                    and next_offset > arguments.get("offset", 0) and matches):
                continue
        # A final BGS page is labelled partial because it omits prior pages; those
        # pages are already retained in this bundle when the sequence began at zero.
        if (
            entry["tool"] == "bgs_features"
            and not (result.get("pagination") or {}).get("next_page")
            and not entry.get("pagination_stop_reason")
        ):
            collection = entry["arguments"].get("collection")
            previous = [
                e
                for e in evidence
                if e["tool"] == "bgs_features" and e["arguments"].get("collection") == collection
                and all(e["arguments"].get(key) == entry["arguments"].get(key)
                        for key in ("bbox", "limit", "include_geometry"))
            ]
            expected = 0
            contiguous = True
            for prior in previous:
                if prior["status"] == "error" or prior["arguments"].get("offset", 0) != expected:
                    contiguous = False
                    break
                expected += len(prior["result"].get("data", []))
            total = (result.get("pagination") or {}).get("total_reported_by_provider")
            accounted_for = (
                isinstance(total, int) and not isinstance(total, bool) and expected >= total
            )
            implicit_final = total is None and entry["arguments"].get("offset", 0) > 0
            if contiguous and (accounted_for or implicit_final):
                continue
        incomplete.append(entry)
    return incomplete

