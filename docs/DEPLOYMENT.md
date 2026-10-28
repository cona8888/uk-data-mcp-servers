# Deployment and access

## Local first

The supported initial deployment is a local MCP client starting the Python
server over stdio. No API keys are required by the implemented provider
adapters. Windows, macOS and Linux use the same Python source. Docker packages
the dependencies but still requires Docker and internet access to the providers.

The optional Streamable HTTP listener binds to `127.0.0.1` by default, provides
the MCP endpoint `/mcp`, and is not a web GUI. The compose file binds the host
port to loopback while the container listens internally on `0.0.0.0`. DNS
rebinding checks only allow local Host/Origin values. The process runs without
root privileges in the container and cannot mutate upstream datasets.

Standard `HTTP_PROXY`/`HTTPS_PROXY` settings are respected for managed networks.
Do not put proxy credentials in project files. The built-in adapters require no
provider credentials and do not expose a general URL fetch primitive.

## Hosted deployment is a separate task

A server running on your laptop is not automatically reachable from a hosted
AI client. Before publishing a remotely reachable MCP service, implement
HTTPS, MCP-compatible authentication/authorization appropriate to the chosen
client, per-user request quotas, monitoring and secret storage. The SDK supports
these integrations; this MVP has not configured or tested them. Do not expose
the unauthenticated local example on a public interface.

Keep provider terms distinct from application permissions. In particular:

- A user's API key may allow access to licensed data without allowing onward
  disclosure to other users or external models.
- NUAR participation does not imply an API entitlement, and its approved uses
  and users are restricted. No NUAR adapter is enabled here.
- An approved cloud model, local model or institutional environment is a
  separate choice from whether a dataset may be downloaded.
- Avoid logging confidential site coordinates or query text without an agreed
  retention policy. The current network layer does not log request payloads.

## Provider maintenance

`sources.json` is reviewed metadata as of 27 October 2026, not a continuously
maintained mirror. Use the opt-in live checks after dependency changes and when
an endpoint changes. Provider failures must remain visible, with no silently
substituted synthetic observations. A production system should maintain
provider health, licence/version changes and audit retention explicitly.
