# vps-guardias — memory guards for the VPS host

Installed manually on 2026-08-18 (CI paused that day); these files are the
source of truth per the manifest doctrine: edit here, never only on the VPS.

Why they exist: tailscaled reached 2.2 GB RSS after 54 days (the CI used to
register a Tailscale node per run and never delete it — 763 dead nodes; fixed
with an ephemeral auth key). The host was swapping; container memory pressure
had silently killed two of Hindsight's port proxies.

| File | Installs to | Does |
|---|---|---|
| `tailscaled-memoria.conf` | `/etc/systemd/system/tailscaled.service.d/` | MemoryHigh=512M, MemoryMax=1G, Restart=always (tailscaled is the only door to the host) |
| `reciclar-tailscaled.sh` | `/usr/local/sbin/` | daily conditional recycle: restarts tailscaled ONLY above 600 MB, verifies it comes back |
| `censar-tailnet.sh` | `/usr/local/sbin/` | daily census of CI nodes in the tailnet; a rising count means the auth key stopped being ephemeral |
| `reciclar-tailscaled.units` | `/etc/systemd/system/` (split in two) | oneshot service + daily 04:15 timer running both scripts |

| `levantar-kb-al-arrancar.sh` | `/usr/local/sbin/` | after a boot, brings the knowledge-base server back up and republishes :443 to Caddy. Idempotent: touches nothing when both are already fine (2026-09-09) |
| `levantar-kb-al-arrancar.units` | `/etc/systemd/system/` (one service) | oneshot after docker+tailscaled, `WantedBy=multi-user.target` |
| `sudoers-kirlts-claude` | `/etc/sudoers.d/` (0440) | full elevation for the account Claude Code runs as, so a session born inside the VPS can administer like one that SSHes in from the notebook (2026-08-20). Validate with `visudo -cf` before installing |
Also applied that day (live `docker update`, pending in compose): memory
limits hindsight=2g, infisical=1g.

Why the 2026-09-09 guard exists: on 2026-09-06 at 03:42 this host went down
dirtily — dockerd logged dozens of `layer not mounted` — and on the way back the
`kb-mcp` container stayed `Exited (255)`: its own `restart: unless-stopped` does
NOT recover a container that died in a dirty shutdown. The :443 publication was
gone too, and that one is `tailscale funnel` — runtime config declared in no
file, so nothing reapplied it. Cost: three days of an unreachable knowledge base
for every remote consumer, unnoticed because nothing watched it. The watching
now lives in kb-okos (`tools/base_responde.py`, a permanent sweep check); this
guard is the other half — that it comes back on its own.

| `renovar-cert-funnel.sh` | `/usr/local/sbin/` | daily: asks Tailscale for the current cert for the Funnel hostname, writes it to `/opt/toolset/certs/`, restarts Caddy only if the cert actually changed |
| `renovar-cert-funnel.units` | `/etc/systemd/system/` (split in two) | oneshot service + daily 05:00 timer |

Why `renovar-cert-funnel.*` exists (2026-09-27): the public :443 Funnel used to
have tailscaled terminate the TLS itself, in its own userspace network stack
(gVisor) — that path carries a known upstream bug
(`tailscale/tailscale#18916`): Nagle plus the client's delayed ACK stall the
handshake by ~220ms, twice per connection, because the ServerHello and the
rest of the flight go out as separate writes. Measured on the public path
(from outside the tailnet, against the real Funnel IPs): median TLS time
~900ms, with 1–3% of probes failing outright. Moving TLS termination into
Caddy (a real Linux socket, not gVisor) and having Tailscale forward :443 as
raw TCP to Caddy's own HTTPS listener (`:8091`, see `Caddyfile`) removes that
stall — the geography (the Funnel's nearest ingress region is in the US, this
host is in Brazil) still costs a real round trip, but the bug's extra ~440ms
no longer piles on top of it. Caddy needs its own copy of the cert Tailscale
already issues for the hostname (`tailscale cert`), and unlike tailscaled's
internal copy, this one does not renew itself — this guard is what keeps it
current.
