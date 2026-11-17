# Funding status (2026-11-17, M0)

Deployer 0x831Ae1004584C3DEfa15aC774C64d95e840131Dc balances:
- Ethereum Sepolia: 0.1849 ETH (after faucet claim 0.295, minus 0.05 conversion, minus 2x 0.03 bridges, minus gas)
- Reactive Lasna: 5.25 lREACT (from sending 0.05 Sepolia ETH to the faucet contract 0x9b9BB25f1A81078C544C829c5EB7822d747Cf434 — conversion confirmed working post-Omni; observed rate 105 lREACT per ETH)
- Unichain Sepolia: 0.03 ETH (bridged from Sepolia, credited)
- Base Sepolia: 0.03 ETH bridge deposit succeeded on L1 but not yet credited on L2 at last check (2026-11-17 18:05 JST) — recheck at M1.

Key txs (all Sepolia):
- Faucet claim 0.295 ETH: 0x18c293c5927bfd1eec3a14841444242097c0dc8d2c2af8ccfdbc03853b33958d (block 12153350)
- lREACT conversion 0.05 ETH: 0x0f640f3fcd7ede5756bd3e6a2c3da735d7f2b4055f0bc0b5765b5d9b17d92930
- Bridge to Base Sepolia 0.03 ETH: 0x0bf4aeb75f0552cf9fd51151474db535737b19ccb4f3ac4234dd7f0a3f78da6a (L1StandardBridge 0xfd0Bf71F60660E2f608ed56e1659C450eB113120)
- Bridge to Unichain Sepolia 0.03 ETH: 0xe03e0276da930c81e226bd210b417c6c5755a63cd0f5691703aee898fa5aac0f (L1StandardBridge 0xea58fca6849d79ead1f26608855c2d6407d54ce2)

Note: the claimed 0.295 SepETH included 0.188 accumulated by the earlier device-browser session (started 17:50 JST) — the pk910 session resumed across browsers.
Still to fund: verdictWriter needs a small Base Sepolia balance for postVerdict gas (send from deployer once Base lands).
