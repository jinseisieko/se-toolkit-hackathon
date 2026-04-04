# How to Use LogSentinel

## 1. Deploy

```bash
git clone https://github.com/jinseisieko/se-toolkit-hackathon.git
cd se-toolkit-hackathon
docker compose up --build -d
```

That's it. The container starts monitoring `/var/log/auth.log` immediately.

---

## 2. Set Your API Token

Edit `.env` and set a secret token:

```env
API_TOKEN=your-secret-token-here
```

This token is required to block/unblock IPs via the API. Without it, those endpoints return `404`.

Restart after changing:
```bash
docker compose restart
```

---

## 3. Open the Dashboard

Navigate to **http://\<VM_IP\>:5000** in your browser.

You'll see:
- **Stats cards** — Total alerts, Active, Blocked
- **Alerts table** — IP, attempts, service, time, status badge
- **Live polling** — updates every 10 seconds

---

## 4. Block an IP (via API)

```bash
curl -X POST http://localhost:5000/api/block \
  -H "Authorization: Bearer your-secret-token-here" \
  -H "Content-Type: application/json" \
  -d '{"ip": "203.0.113.50", "reason": "brute-force detected"}'
```

Response:
```json
{"blocked": true, "ip": "203.0.113.50", "reason": "brute-force detected"}
```

The IP appears in the dashboard as **Blocked** (red badge).

---

## 5. Unblock an IP (via API)

```bash
curl -X POST http://localhost:5000/api/unblock \
  -H "Authorization: Bearer your-secret-token-here" \
  -H "Content-Type: application/json" \
  -d '{"ip": "203.0.113.50"}'
```

Response:
```json
{"blocked": false, "ip": "203.0.113.50"}
```

The IP changes to **Active** (green badge) on the dashboard.

---

## 6. View Alerts (JSON API)

```bash
curl http://localhost:5000/api/alerts
```

```json
[
  {
    "ip": "203.0.113.50",
    "attempts": 5,
    "service": "ssh",
    "first_seen": "2026-04-04T10:51:08+00:00",
    "last_seen": "2026-04-04T10:51:08+00:00",
    "blocked": true
  }
]
```

No authentication needed.

---

## 7. Monitor Metrics (Prometheus)

```bash
curl http://localhost:5000/metrics
```

```
logsentinel_alerts_total{service="ssh"} 3
logsentinel_blocks_total{strategy="NoOpStrategy"} 2
logsentinel_parse_duration_seconds{parser="ssh_auth",quantile="avg"} 0.005155
```

Scrape this endpoint with Prometheus or check manually.

---

## 8. View Container Logs

```bash
docker logs logsentinel -f
```

You'll see real-time detection events:
```
BREACH: ssh — 5 attempts from 203.0.113.50
[TEST MODE] Would block 203.0.113.50: SSH brute-force: 5 attempts
Auto-blocked 203.0.113.50 via NoOpStrategy
🔴 [SSH] failed_auth
   IP: 203.0.113.50
   Time: 2026-04-04 10:51:08 UTC
```

---

## 9. Change Detection Threshold

Edit `.env`:

```env
BLOCK_THRESHOLD=3    # Alert after 3 failures (default: 5)
```

Restart: `docker compose restart`

---

## 10. Enable Real Firewall Blocking

In `.env`:

```env
FIREWALL_STRATEGY=ufw
```

Restart: `docker compose up --build -d`

⚠️ **Warning:** This will actually block IPs on the host via `ufw`. Use with caution.

---

## Quick Reference

| Task | Command / URL |
|------|---------------|
| Open dashboard | `http://<VM_IP>:5000` |
| Block IP | `POST /api/block` with Bearer token |
| Unblock IP | `POST /api/unblock` with Bearer token |
| List alerts | `GET /api/alerts` |
| List blocked | `GET /api/blocked` |
| View metrics | `GET /metrics` |
| Follow logs | `docker logs logsentinel -f` |
| Restart | `docker compose restart` |
| Stop | `docker compose down` |
| Update | `git pull && docker compose up --build -d` |
