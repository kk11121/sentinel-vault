# Demo video runbook (2-3 min, English subtitles, no owner voice)

## Pre-flight (do not film)
- [ ] Worker running the MODEL version; log shows current modelHash.
      Restart it >10 min before filming so its startup rescan of stale
      requests (and any surprise verdicts/freezes) settles first.
- [ ] All 3 vaults unfrozen; top up Base vault so a normal withdrawal
      has balance_ratio ~0.1-0.2 (deposit testnet ETH to ~0.05 ETH).
- [ ] Set Base vault wait to 60 s for filming (owner setWait), restore
      180 s after. Threshold stays 0.02 ETH... note: filming amounts
      must be >= threshold to enter the queue; use 0.025 ETH normal /
      0.025 ETH suspicious if balance allows, else lower threshold
      to 0.004 for the shoot and say so in the caption.
- [ ] Explorer tabs pre-opened: Base vault, registry, Sepolia vault.
- [ ] Terminal with cast commands pre-typed (history), worker log tail.

## Shot list / script (captions in English)
1. (0:00-0:20) Title + one-liner. Caption: "Sentinel Vault: an AI
   judges every withdrawal. A Reactive contract does the stopping.
   The AI's key can never move funds."
2. (0:20-0:50) Normal flow: requestWithdrawal (known address) ->
   worker log shows LOW -> wait -> executeWithdrawal succeeds.
   Caption: "Normal withdrawal: judged LOW, executes after the
   timelock. If the AI were silent, it would still execute: fail-open."
3. (0:50-1:30) Attack flow: requestWithdrawal to a first-seen address
   -> worker log shows MEDIUM/HIGH with features -> verdict tx on
   Basescan -> veto lands; executeWithdrawal reverts Vetoed.
   Caption: "Suspicious withdrawal: the model flags it, the verdict
   goes on-chain, and the Reactive contract vetoes it — no server
   in the enforcement path."
4. (1:30-2:10) Escalation: second suspicious request -> all three
   vaults frozen; show frozen()==true on Sepolia + Unichain explorers.
   Caption: "A second flag within an hour freezes every vault,
   pre-emptively, across three chains."
5. (2:10-2:40) Audit: run scripts/replay.py on the attack verdict ->
   all MATCH. Show model.json + MODEL_CARD + eval table briefly.
   Caption: "Every verdict carries the model hash and feature hash.
   Anyone can replay it. Our eval numbers are published as computed —
   including the false alarms."
6. (2:40-3:00) End card: repo URL + addresses. Caption: "Sentinel
   Vault — auditable after the fact, bounded damage by design."

## Post-flight
- [ ] Restore wait=180 s; leave vaults unfrozen; worker may keep running.
- [ ] Record the filmed run's tx hashes into docs/deployments.md.
