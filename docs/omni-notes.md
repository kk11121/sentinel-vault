# Omni notes — Reactive Lasna after the Omni fork (compiled 2026-11-17)

Sources (primary):
- Migration announcement: https://blog.reactive.network/reactives-next-chapter-starts-testnet-launch-team-news/ (Omni fork rolled out on Lasna 2026-05-25)
- Lasna migration complete: https://blog.reactive.network/lasna-testnet-completes-migration-to-omni-fork/ (2026-10-07)
- Mainnet migration complete: https://blog.reactive.network/reactive-mainnet-migration-complete/ (2026-10-28)
- Origins & Destinations: https://dev.reactive.network/origins-and-destinations
- Economy & System Interactions: https://dev.reactive.network/economy

## What changed with Omni
- RVM is gone. Reactive contracts deploy once, to a single environment, as standard Solidity (0.8.29). No dual deployment, no RVM dual state.
- CometBFT consensus: ~1s blocks, instant finality (no reorgs).
- Subscriptions keep the same signature; a new system contract handles them.
- Callbacks: legacy event format is supported indefinitely; new contracts may instead call a system-contract method to request a callback.
- System contract address (unchanged): 0x8888888888888888888888888888888888888888
- Economy (from /economy, crawled 2026-11-17): every reactive tx runs through the system contract's trigger(); a contract with debt > 0 goes inactive (system will not call react(), proxy will not deliver callbacks) until debt is covered. Max reactive tx gas 900,000. Minimum callback gas limit 100,000.

## Network endpoints
- Chain ID 5318007, currency lREACT.
- Docs/blog give RPC https://lasna-omni-rpc.rnk.dev and explorer https://lasna-omni.reactscan.net.
- VM check 2026-11-17: the omni hostnames do not respond from Muse's VM (empty reply / TLS close), while the legacy hostnames answer live: https://lasna-rpc.rnk.dev returns chainId 5318007 at block ~8.5M and https://lasna.reactscan.net returns HTTP 200. Treat legacy hostnames as working aliases of the migrated chain; re-check at M1 deployment time.

## Callback proxies (testnet, from Origins & Destinations)
- Base Sepolia (84532): 0x476F44b11F5C942c58f4c8E3d0300E5710743585
- Ethereum Sepolia (11155111): 0xAa14d9Cd0f788Ca23d11805986C1d8bd035D23b4 (per Claude's instruction doc; the docs search excerpt confirmed Base and Unichain values verbatim — re-verify this one on the page at M1)
- Unichain Sepolia (1301): 0x775c9B990ADe401060B78D0e98684eEf8d2466C1
- Destination-side validation: msg.sender must be the chain's callback proxy AND the original sender must be Reactive Signer.

## Still to confirm at M1 (do not let code depend on these until confirmed)
- Exact Omni system-contract API names for subscribe / callback request (Claude's doc names SYSTEM.subscribe(...), SYSTEM.requestCallbackV_1_0(...) with CallbackConfiguration_V_1_0, and react(...) external onlySystem taking LogRecord memory — plausible but not yet read verbatim in docs text).
- Faucet contract addresses and the Sepolia ETH -> lREACT rate under Omni (legacy page said 1 ETH -> 100 lREACT via 0x9b9BB25f1A81078C544C829c5EB7822d747Cf434 on Ethereum Sepolia / 0x2afaFD298b23b62760711756088F75B7409f5967 on Base Sepolia — re-verify).
- Whether legacy vmOnly-style contracts still deploy/run on Lasna (docs say legacy is supported; only relevant as a fallback).
