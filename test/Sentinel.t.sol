// SPDX-License-Identifier: MIT
pragma solidity ^0.8.29;

import { Test } from "forge-std/Test.sol";
import { VerdictRegistry } from "../src/contracts/VerdictRegistry.sol";
import { GuardedVault } from "../src/contracts/GuardedVault.sol";
import { SentinelReactive } from "../src/contracts/SentinelReactive.sol";
import { ISystemContract } from "../src/interfaces/ISystemContract.sol";
import { LogRecord } from "../src/interfaces/IReactive.sol";
import { OmniCallback } from "../src/base/OmniCallback.sol";

contract SystemStub {
    uint256 public callbackCount;
    uint256 public subscribeCount;
    bytes[] public payloads;
    address[] public recipients;

    function subscribe(uint256, address, uint256, uint256, uint256, uint256) external {
        subscribeCount++;
    }

    function requestCallbackV_1_0(ISystemContract.CallbackConfiguration_V_1_0 memory config_) external {
        callbackCount++;
        payloads.push(config_.payload);
        recipients.push(config_.recipient);
    }

    function debts(address) external pure returns (uint256) {
        return 0;
    }

    fallback() external payable { }
}

contract SentinelTest is Test {
    address owner = address(0xA11CE);
    address recovery = address(0x12EC0);
    address writer = address(0xB0B);
    address attacker = address(0xBAD);
    address proxy = address(0xCA11BAC);
    address system = 0x8888888888888888888888888888888888888888;
    address user = address(0x555E12);

    uint256 constant VAULT_CHAIN = 11155111; // the vault lives on Sepolia in these tests

    bytes4 constant VETO_SEL = bytes4(keccak256("veto(address,uint256)"));
    bytes4 constant FREEZE_SEL = bytes4(keccak256("freeze(address,bytes32)"));

    VerdictRegistry registry;
    GuardedVault vault;
    SentinelReactive rsc;
    SystemStub stub;

    function setUp() public {
        stub = new SystemStub();
        vm.etch(system, address(stub).code);
        // vm.etch copies code but not storage; point the counter reads at the stub instance.
        registry = new VerdictRegistry(owner, writer);
        rsc = new SentinelReactive(address(registry));
        vault = new GuardedVault(owner, recovery, proxy, address(rsc), 600, 0.02 ether, 0.008 ether, 1 hours);
        vm.deal(address(vault), 1 ether);
        rsc.watchVault(VAULT_CHAIN, address(vault));
    }

    function _callbacks() internal view returns (uint256) {
        return SystemStub(payable(system)).callbackCount();
    }

    function _payloadSel(uint256 i) internal view returns (bytes4 sel) {
        bytes memory p = SystemStub(payable(system)).payloads(i);
        assembly {
            sel := mload(add(p, 32))
        }
    }

    function _verdictLog(uint256 requestId, address vault_, uint8 severity) internal view returns (LogRecord memory log_) {
        return _verdictLogOn(VAULT_CHAIN, requestId, vault_, severity);
    }

    function _verdictLogOn(uint256 chainId, uint256 requestId, address vault_, uint8 severity)
        internal
        view
        returns (LogRecord memory log_)
    {
        log_.chainId = 84532;
        log_.contractAddress = address(registry);
        log_.topic0 = uint256(keccak256("VerdictPosted(uint256,address,uint256,uint8,uint256,bytes32,bytes32)"));
        log_.topic1 = chainId;
        log_.topic2 = uint256(uint160(vault_));
        log_.topic3 = requestId;
        log_.data = abi.encode(severity, uint256(900), bytes32(0), bytes32(0));
    }

    function _withdrawalLog(uint256 requestId, address vault_) internal view returns (LogRecord memory log_) {
        return _withdrawalLogOn(VAULT_CHAIN, requestId, vault_);
    }

    function _withdrawalLogOn(uint256 chainId, uint256 requestId, address vault_)
        internal
        view
        returns (LogRecord memory log_)
    {
        log_.chainId = chainId;
        log_.contractAddress = vault_;
        log_.topic0 = uint256(keccak256("WithdrawalRequested(uint256,address,address,uint256,uint256)"));
        log_.topic1 = requestId;
        log_.topic2 = uint256(uint160(owner));
        log_.topic3 = uint256(uint160(user));
        log_.data = abi.encode(uint256(0.05 ether), block.timestamp);
    }

    // ---------- VerdictRegistry ----------

    function test_postVerdict_onlyWriter() public {
        vm.prank(attacker);
        vm.expectRevert(VerdictRegistry.NotVerdictWriter.selector);
        registry.postVerdict(VAULT_CHAIN, address(vault), 1, 2, 900, bytes32(0), bytes32(0));
        vm.prank(writer);
        registry.postVerdict(VAULT_CHAIN, address(vault), 1, 2, 900, bytes32(0), bytes32(0));
        assertTrue(registry.hasVerdict(VAULT_CHAIN, address(vault), 1));
    }

    function test_postVerdict_duplicateReverts() public {
        vm.prank(writer);
        registry.postVerdict(VAULT_CHAIN, address(vault), 1, 0, 100, bytes32(0), bytes32(0));
        vm.prank(writer);
        vm.expectRevert(VerdictRegistry.DuplicateVerdict.selector);
        registry.postVerdict(VAULT_CHAIN, address(vault), 1, 2, 900, bytes32(0), bytes32(0));
    }

    function test_setVerdictWriter_rotation() public {
        address writer2 = address(0xCA7);
        vm.prank(attacker);
        vm.expectRevert(VerdictRegistry.NotOwner.selector);
        registry.setVerdictWriter(writer2);
        vm.prank(owner);
        registry.setVerdictWriter(writer2);
        vm.prank(writer);
        vm.expectRevert(VerdictRegistry.NotVerdictWriter.selector);
        registry.postVerdict(VAULT_CHAIN, address(vault), 1, 0, 100, bytes32(0), bytes32(0));
        vm.prank(writer2);
        registry.postVerdict(VAULT_CHAIN, address(vault), 1, 0, 100, bytes32(0), bytes32(0));
        assertTrue(registry.hasVerdict(VAULT_CHAIN, address(vault), 1));
    }

    // ---------- GuardedVault: permissions ----------

    function test_requestWithdrawal_onlyOwner() public {
        vm.prank(attacker);
        vm.expectRevert(GuardedVault.NotOwner.selector);
        vault.requestWithdrawal(attacker, 0.001 ether);
        vm.prank(user);
        vm.expectRevert(GuardedVault.NotOwner.selector);
        vault.requestWithdrawal(user, 0.001 ether);
        vm.prank(owner);
        uint256 id = vault.requestWithdrawal(user, 0.001 ether);
        assertEq(id, 1);
    }

    function test_settings_recoveryOnly() public {
        vm.prank(owner);
        vm.expectRevert(GuardedVault.NotRecovery.selector);
        vault.setWait(0);
        vm.prank(owner);
        vm.expectRevert(GuardedVault.NotRecovery.selector);
        vault.setThreshold(100 ether);
        vm.prank(owner);
        vm.expectRevert(GuardedVault.NotRecovery.selector);
        vault.setInstantCap(100 ether, 1 hours);
        vm.prank(recovery);
        vault.setWait(300);
        assertEq(vault.waitSeconds(), 300);
        vm.prank(recovery);
        vault.setThreshold(0.05 ether);
        assertEq(vault.largeThreshold(), 0.05 ether);
    }

    function test_unfreeze_recoveryOnly() public {
        vm.prank(proxy);
        vault.freeze(address(rsc), bytes32("HIGH_VERDICT"));
        assertTrue(vault.frozen());
        vm.prank(owner);
        vm.expectRevert(GuardedVault.NotRecovery.selector);
        vault.unfreeze();
        assertTrue(vault.frozen());
        vm.prank(recovery);
        vault.unfreeze();
        assertFalse(vault.frozen());
    }

    function test_freeze_directCallFails() public {
        vm.prank(attacker);
        vm.expectRevert();
        vault.freeze(address(rsc), bytes32("HIGH_VERDICT"));
        assertFalse(vault.frozen());
    }

    function test_freeze_viaProxySucceeds() public {
        vm.prank(proxy);
        vault.freeze(address(rsc), bytes32("HIGH_VERDICT"));
        assertTrue(vault.frozen());
    }

    function test_freeze_idempotent() public {
        vm.prank(proxy);
        vault.freeze(address(rsc), bytes32("HIGH_VERDICT"));
        vm.prank(proxy);
        vault.freeze(address(rsc), bytes32("HIGH_VERDICT")); // duplicate: no revert
        assertTrue(vault.frozen());
    }

    function test_constructor_zeroChecks() public {
        vm.expectRevert(OmniCallback.ZeroAddress.selector);
        new GuardedVault(address(0), recovery, proxy, address(rsc), 600, 0.02 ether, 0.008 ether, 1 hours);
        vm.expectRevert(OmniCallback.ZeroAddress.selector);
        new GuardedVault(owner, address(0), proxy, address(rsc), 600, 0.02 ether, 0.008 ether, 1 hours);
        vm.expectRevert(GuardedVault.ZeroWindow.selector);
        new GuardedVault(owner, recovery, proxy, address(rsc), 600, 0.02 ether, 0.008 ether, 0);
    }

    function test_pay_onlyProxy() public {
        vm.deal(proxy, 0 ether);
        vm.prank(proxy);
        vault.pay(0.1 ether);
        assertEq(proxy.balance, 0.1 ether);
        vm.prank(attacker);
        vm.expectRevert();
        vault.pay(0.1 ether);
    }

    // ---------- GuardedVault: request validation (audit F5/F9/F13) ----------

    function test_request_zeroAmountReverts() public {
        vm.prank(owner);
        vm.expectRevert(GuardedVault.ZeroAmount.selector);
        vault.requestWithdrawal(user, 0);
    }

    function test_request_invalidDestinationReverts() public {
        vm.prank(owner);
        vm.expectRevert(GuardedVault.InvalidDestination.selector);
        vault.requestWithdrawal(address(0), 0.001 ether);
        vm.prank(owner);
        vm.expectRevert(GuardedVault.InvalidDestination.selector);
        vault.requestWithdrawal(address(vault), 0.001 ether);
    }

    function test_pendingReservation_aggregate() public {
        // Balance is 1 ETH. Two queued 0.5 ETH requests reserve the whole
        // balance; a third request of any size must fail until one of the
        // pending requests resolves.
        vm.startPrank(owner);
        uint256 idA = vault.requestWithdrawal(user, 0.5 ether);
        uint256 idB = vault.requestWithdrawal(user, 0.5 ether);
        vm.expectRevert(GuardedVault.InsufficientBalance.selector);
        vault.requestWithdrawal(user, 0.1 ether);
        vm.stopPrank();
        assertEq(vault.pendingTotal(), 1 ether);
        // Executing A frees balance but B still reserves the rest.
        vm.warp(block.timestamp + 601);
        vault.executeWithdrawal(idA);
        assertEq(vault.pendingTotal(), 0.5 ether);
        vm.prank(owner);
        vm.expectRevert(GuardedVault.InsufficientBalance.selector);
        vault.requestWithdrawal(user, 0.1 ether);
        // Vetoing B releases its reservation entirely.
        vm.prank(proxy);
        vault.veto(address(rsc), idB);
        assertEq(vault.pendingTotal(), 0);
        vm.prank(owner);
        vault.requestWithdrawal(user, 0.4 ether);
        assertEq(vault.pendingTotal(), 0.4 ether);
    }

    // ---------- GuardedVault: owner rotation (audit F7) ----------

    function test_ownerRotation_fullFlow() public {
        address newOwner = address(0xBEEF1);
        // Only recovery proposes.
        vm.prank(owner);
        vm.expectRevert(GuardedVault.NotRecovery.selector);
        vault.proposeOwner(newOwner);
        vm.prank(recovery);
        vault.proposeOwner(newOwner);
        assertEq(vault.pendingOwner(), newOwner);
        // Too early to finalize.
        vm.expectRevert(GuardedVault.RotationNotReady.selector);
        vault.finalizeOwnerRotation();
        // Owner can cancel.
        vm.prank(owner);
        vault.cancelOwnerRotation();
        assertEq(vault.pendingOwner(), address(0));
        // Propose again, wait out the delay, anyone finalizes.
        vm.prank(recovery);
        vault.proposeOwner(newOwner);
        vm.warp(block.timestamp + 48 hours);
        vault.finalizeOwnerRotation();
        assertEq(vault.owner(), newOwner);
        // The new owner can request; the old one cannot.
        vm.prank(owner);
        vm.expectRevert(GuardedVault.NotOwner.selector);
        vault.requestWithdrawal(user, 0.001 ether);
        vm.prank(newOwner);
        uint256 id = vault.requestWithdrawal(user, 0.001 ether);
        assertGt(id, 0);
    }

    // ---------- GuardedVault: withdrawal flow ----------

    function test_largeWithdrawal_waitsThenExecutes() public {
        vm.prank(owner);
        uint256 id = vault.requestWithdrawal(user, 0.05 ether);
        vm.expectRevert(GuardedVault.NotReady.selector);
        vault.executeWithdrawal(id);
        vm.warp(block.timestamp + 601);
        uint256 before = user.balance;
        vault.executeWithdrawal(id);
        assertEq(user.balance - before, 0.05 ether);
    }

    function test_smallWithdrawal_immediate() public {
        vm.prank(owner);
        uint256 id = vault.requestWithdrawal(user, 0.001 ether);
        uint256 before = user.balance;
        vault.executeWithdrawal(id);
        assertEq(user.balance - before, 0.001 ether);
    }

    function test_instantCap_barrageQueuesExcess() public {
        // cap is 0.008 ether per hour; three 0.003 requests in one block:
        // the first two are instant, the third must queue.
        vm.startPrank(owner);
        uint256 id1 = vault.requestWithdrawal(user, 0.003 ether);
        uint256 id2 = vault.requestWithdrawal(user, 0.003 ether);
        uint256 id3 = vault.requestWithdrawal(user, 0.003 ether);
        vm.stopPrank();
        (,, uint256 amount3, uint256 readyAt3,,,) = vault.withdrawals(id3);
        assertEq(amount3, 0.003 ether);
        assertEq(readyAt3, block.timestamp + 600);
        vault.executeWithdrawal(id1);
        vault.executeWithdrawal(id2);
        vm.expectRevert(GuardedVault.NotReady.selector);
        vault.executeWithdrawal(id3);
        // After the window passes the instant budget resets.
        vm.warp(block.timestamp + 3601);
        vm.prank(owner);
        uint256 id4 = vault.requestWithdrawal(user, 0.003 ether);
        (,,, uint256 readyAt4,,,) = vault.withdrawals(id4);
        assertEq(readyAt4, block.timestamp);
    }

    function test_instantCap_exactEqualityIsInstant() public {
        vm.startPrank(owner);
        uint256 id1 = vault.requestWithdrawal(user, 0.004 ether);
        uint256 id2 = vault.requestWithdrawal(user, 0.004 ether); // spent == cap exactly
        uint256 id3 = vault.requestWithdrawal(user, 0.001 ether); // over: queues
        vm.stopPrank();
        (,,, uint256 readyAt2,,,) = vault.withdrawals(id2);
        assertEq(readyAt2, block.timestamp);
        (,,, uint256 readyAt3,,,) = vault.withdrawals(id3);
        assertEq(readyAt3, block.timestamp + 600);
        vault.executeWithdrawal(id1);
        vault.executeWithdrawal(id2);
    }

    function test_setInstantCap_resetsWindow() public {
        vm.startPrank(owner);
        vault.requestWithdrawal(user, 0.003 ether);
        vault.requestWithdrawal(user, 0.003 ether); // 0.006 of the 0.008 cap spent
        vm.stopPrank();
        vm.prank(recovery);
        vault.setInstantCap(0.008 ether, 1 hours); // resets the window
        vm.prank(owner);
        uint256 id = vault.requestWithdrawal(user, 0.003 ether);
        (,,, uint256 readyAt,,,) = vault.withdrawals(id);
        assertEq(readyAt, block.timestamp); // instant again under the fresh window
    }

    function test_veto_blocksExecution() public {
        vm.prank(owner);
        uint256 id = vault.requestWithdrawal(attacker, 0.05 ether);
        vm.prank(proxy);
        vault.veto(address(rsc), id);
        vm.warp(block.timestamp + 601);
        vm.expectRevert(GuardedVault.Vetoed.selector);
        vault.executeWithdrawal(id);
    }

    function test_veto_directCallFails() public {
        vm.prank(owner);
        uint256 id = vault.requestWithdrawal(attacker, 0.05 ether);
        vm.prank(attacker);
        vm.expectRevert();
        vault.veto(address(rsc), id);
    }

    function test_veto_afterExecution_noRevert() public {
        vm.prank(owner);
        uint256 id = vault.requestWithdrawal(user, 0.001 ether);
        vault.executeWithdrawal(id);
        vm.prank(proxy);
        vault.veto(address(rsc), id); // too late: must not revert
    }

    function test_frozen_blocksWithdrawals() public {
        vm.prank(proxy);
        vault.freeze(address(rsc), bytes32("HIGH_VERDICT"));
        vm.prank(owner);
        vm.expectRevert(GuardedVault.VaultFrozen.selector);
        vault.requestWithdrawal(user, 0.001 ether);
    }

    function test_executeWhileFrozen_reverts() public {
        vm.prank(owner);
        uint256 id = vault.requestWithdrawal(user, 0.05 ether);
        vm.prank(proxy);
        vault.freeze(address(rsc), bytes32("HIGH_VERDICT"));
        vm.warp(block.timestamp + 601);
        vm.expectRevert(GuardedVault.VaultFrozen.selector);
        vault.executeWithdrawal(id);
        // After a recovery unfreeze the (unvetoed) request executes.
        vm.prank(recovery);
        vault.unfreeze();
        vault.executeWithdrawal(id);
    }

    // ---------- SentinelReactive ----------

    function test_react_onlySystem() public {
        vm.prank(attacker);
        vm.expectRevert();
        rsc.react(_verdictLog(7, address(vault), 2));
    }

    function test_react_mediumKnownRequest_vetoes() public {
        vm.prank(system);
        rsc.react(_withdrawalLog(1, address(vault)));
        vm.prank(system);
        rsc.react(_verdictLog(1, address(vault), 1));
        assertGt(rsc.lastMediumAt(rsc.vaultKey(VAULT_CHAIN, address(vault))), 0);
        assertEq(_callbacks(), 1); // exactly one veto callback
        assertEq(_payloadSel(0), VETO_SEL);
    }

    // F2: a MEDIUM that arrives before its request is buffered, not dropped.
    function test_react_mediumBeforeRequest_appliedOnArrival() public {
        vm.prank(system);
        rsc.react(_verdictLog(99, address(vault), 1));
        assertEq(_callbacks(), 0); // nothing yet
        assertEq(rsc.pendingVetoes(rsc.requestKey(VAULT_CHAIN, address(vault), 99)), 1);
        vm.prank(system);
        rsc.react(_withdrawalLog(99, address(vault)));
        assertEq(_callbacks(), 1); // the veto fires on arrival
        assertEq(_payloadSel(0), VETO_SEL);
        assertEq(rsc.pendingVetoes(rsc.requestKey(VAULT_CHAIN, address(vault), 99)), 0);
    }

    // F1: a HIGH vetoes its own request as well as freezing.
    function test_react_highKnownRequest_vetoesAndFreezes() public {
        vm.prank(system);
        rsc.react(_withdrawalLog(5, address(vault)));
        vm.prank(system);
        rsc.react(_verdictLog(5, address(vault), 2));
        assertEq(_callbacks(), 2); // veto + freeze (one vault watched)
        assertEq(_payloadSel(0), VETO_SEL);
        assertEq(_payloadSel(1), FREEZE_SEL);
    }

    // F1+F2: a HIGH for an unseen request freezes immediately and vetoes
    // the request when it shows up.
    function test_react_highUnknown_freezesNowVetoesOnArrival() public {
        vm.prank(system);
        rsc.react(_verdictLog(99, address(vault), 2));
        assertEq(_callbacks(), 1); // freeze only, for now
        assertEq(_payloadSel(0), FREEZE_SEL);
        vm.prank(system);
        rsc.react(_withdrawalLog(99, address(vault)));
        assertEq(_callbacks(), 2); // the pending veto lands
        assertEq(_payloadSel(1), VETO_SEL);
    }

    function test_react_verdictFromWrongSource_ignored() public {
        LogRecord memory log_ = _verdictLog(1, address(vault), 2);
        log_.contractAddress = attacker;
        vm.prank(system);
        rsc.react(log_);
        assertEq(_callbacks(), 0);
    }

    function test_escalation_atExactlyOneHour() public {
        vm.prank(system);
        rsc.react(_withdrawalLog(1, address(vault)));
        vm.prank(system);
        rsc.react(_verdictLog(1, address(vault), 1));
        assertEq(_callbacks(), 1);
        vm.warp(block.timestamp + 3600); // exactly at the window edge: escalates
        vm.prank(system);
        rsc.react(_withdrawalLog(2, address(vault)));
        vm.prank(system);
        rsc.react(_verdictLog(2, address(vault), 1));
        // Escalation now sends veto + freeze for the escalating request.
        assertEq(_callbacks(), 3);
        assertEq(_payloadSel(1), VETO_SEL);
        assertEq(_payloadSel(2), FREEZE_SEL);
    }

    function test_noEscalation_afterOneHour() public {
        vm.prank(system);
        rsc.react(_withdrawalLog(1, address(vault)));
        vm.prank(system);
        rsc.react(_verdictLog(1, address(vault), 1));
        vm.warp(block.timestamp + 3601); // past the window: veto only
        vm.prank(system);
        rsc.react(_withdrawalLog(2, address(vault)));
        vm.prank(system);
        rsc.react(_verdictLog(2, address(vault), 1));
        assertEq(_callbacks(), 2); // two vetoes, no freeze
        // distinguish veto vs freeze by a third probe: another MEDIUM now escalates
        // against the second one's timestamp, proving the second was recorded as MEDIUM.
        vm.prank(system);
        rsc.react(_withdrawalLog(3, address(vault)));
        vm.prank(system);
        rsc.react(_verdictLog(3, address(vault), 1));
        assertEq(_callbacks(), 4); // veto + freeze (one vault)
    }

    // F3: the same vault address on two chains keeps separate escalation
    // state and correct veto routing.
    function test_sameVaultAddress_twoChains_noFalseEscalation() public {
        uint256 chainB = 1301;
        rsc.watchVault(chainB, address(vault)); // same address, other chain
        // MEDIUM on chain A.
        vm.prank(system);
        rsc.react(_withdrawalLog(1, address(vault)));
        vm.prank(system);
        rsc.react(_verdictLog(1, address(vault), 1));
        assertEq(_callbacks(), 1);
        // MEDIUM for the same address on chain B within the hour: a veto
        // routed to chain B, NOT an escalation.
        vm.prank(system);
        rsc.react(_withdrawalLogOn(chainB, 1, address(vault)));
        vm.prank(system);
        rsc.react(_verdictLogOn(chainB, 1, address(vault), 1));
        assertEq(_callbacks(), 2);
        assertEq(_payloadSel(1), VETO_SEL);
        assertEq(SystemStub(payable(system)).recipients(1), address(vault));
        // A second MEDIUM on chain A does escalate (veto + freeze x2 vaults).
        vm.prank(system);
        rsc.react(_withdrawalLog(2, address(vault)));
        vm.prank(system);
        rsc.react(_verdictLog(2, address(vault), 1));
        assertEq(_callbacks(), 5);
    }

    // F4: a vault watched on a chain outside the original three is frozen too.
    function test_fourthChainVault_frozenByHigh() public {
        address vault4 = address(0xF04);
        rsc.watchVault(999, vault4);
        vm.prank(system);
        rsc.react(_verdictLog(7, address(vault), 2)); // unknown HIGH on the known vault
        assertEq(_callbacks(), 2); // freeze reaches both watched vaults
    }

    // F8: re-registering the same (chain, vault) must not re-subscribe.
    function test_watchVault_idempotent() public {
        uint256 subs = SystemStub(payable(system)).subscribeCount();
        rsc.watchVault(VAULT_CHAIN, address(vault)); // duplicate
        assertEq(SystemStub(payable(system)).subscribeCount(), subs);
        assertEq(rsc.watchedChainCount(), 1);
    }

    function test_paceFreeze_afterLimit() public {
        for (uint256 i = 1; i <= 10; i++) {
            vm.prank(system);
            rsc.react(_withdrawalLog(i, address(vault)));
        }
        assertEq(_callbacks(), 0);
        assertFalse(rsc.paceFrozen());
        vm.prank(system);
        rsc.react(_withdrawalLog(11, address(vault))); // 11th within the hour
        assertTrue(rsc.paceFrozen());
        assertEq(_callbacks(), 1); // freeze-all: one callback per configured vault
        vm.prank(system);
        rsc.react(_withdrawalLog(12, address(vault))); // no repeated freeze storm
        assertEq(_callbacks(), 1);
    }

    function test_paceWindow_resetsAfterHour() public {
        for (uint256 i = 1; i <= 10; i++) {
            vm.prank(system);
            rsc.react(_withdrawalLog(i, address(vault)));
        }
        vm.warp(block.timestamp + 3601); // window slides
        for (uint256 i = 11; i <= 20; i++) {
            vm.prank(system);
            rsc.react(_withdrawalLog(i, address(vault)));
        }
        assertFalse(rsc.paceFrozen());
        assertEq(_callbacks(), 0);
        vm.prank(system);
        rsc.react(_withdrawalLog(21, address(vault))); // 11th in the new window
        assertTrue(rsc.paceFrozen());
        assertEq(_callbacks(), 1);
    }

    // ---------- v6: cancel ----------

    function test_cancel_requesterReleasesReservation() public {
        vm.prank(owner);
        uint256 id = vault.requestWithdrawal(user, 0.05 ether);
        assertEq(vault.pendingTotal(), 0.05 ether);
        vm.prank(owner);
        vault.cancelWithdrawal(id);
        assertEq(vault.pendingTotal(), 0);
        (,,,,, bool executed, bool cancelled) = vault.withdrawals(id);
        assertTrue(cancelled);
        assertFalse(executed);
    }

    function test_cancel_byRecovery() public {
        vm.prank(owner);
        uint256 id = vault.requestWithdrawal(user, 0.05 ether);
        vm.prank(recovery);
        vault.cancelWithdrawal(id);
        assertEq(vault.pendingTotal(), 0);
    }

    function test_cancel_strangerReverts() public {
        vm.prank(owner);
        uint256 id = vault.requestWithdrawal(user, 0.05 ether);
        vm.prank(attacker);
        vm.expectRevert(GuardedVault.NotRequester.selector);
        vault.cancelWithdrawal(id);
    }

    function test_executeCancelled_reverts() public {
        vm.prank(owner);
        uint256 id = vault.requestWithdrawal(user, 0.05 ether);
        vm.prank(owner);
        vault.cancelWithdrawal(id);
        vm.warp(block.timestamp + 601);
        vm.expectRevert(GuardedVault.Cancelled.selector);
        vault.executeWithdrawal(id);
    }

    function test_cancel_terminalStates_revert() public {
        // executed
        vm.prank(owner);
        uint256 id1 = vault.requestWithdrawal(user, 0.001 ether); // instant-sized
        vault.executeWithdrawal(id1);
        vm.prank(owner);
        vm.expectRevert(GuardedVault.AlreadyExecuted.selector);
        vault.cancelWithdrawal(id1);
        // vetoed
        vm.prank(owner);
        uint256 id2 = vault.requestWithdrawal(user, 0.05 ether);
        vm.prank(proxy);
        vault.veto(address(rsc), id2);
        vm.prank(owner);
        vm.expectRevert(GuardedVault.Vetoed.selector);
        vault.cancelWithdrawal(id2);
        // double cancel
        vm.prank(owner);
        uint256 id3 = vault.requestWithdrawal(user, 0.05 ether);
        vm.prank(owner);
        vault.cancelWithdrawal(id3);
        vm.prank(owner);
        vm.expectRevert(GuardedVault.AlreadyCancelled.selector);
        vault.cancelWithdrawal(id3);
        // unknown
        vm.prank(owner);
        vm.expectRevert(GuardedVault.UnknownRequest.selector);
        vault.cancelWithdrawal(999);
    }

    // ---------- v6: RSC watched-check (M1) and idempotency (M6) ----------

    function test_react_verdictForUnwatchedVault_ignored() public {
        address foreign = address(0xDEAD);
        // HIGH about a vault the RSC does not watch: no freeze, no veto,
        // no pending veto recorded.
        vm.prank(system);
        rsc.react(_verdictLog(7, foreign, 2));
        assertEq(_callbacks(), 0);
        assertEq(rsc.pendingVetoes(rsc.requestKey(VAULT_CHAIN, foreign, 7)), 0);
        // The watched vault's address named on an unwatched chain: ignored too.
        vm.prank(system);
        rsc.react(_verdictLogOn(999, 7, address(vault), 2));
        assertEq(_callbacks(), 0);
        // MEDIUM for the foreign vault: no escalation state either.
        vm.prank(system);
        rsc.react(_verdictLog(8, foreign, 1));
        assertEq(_callbacks(), 0);
        assertEq(rsc.lastMediumAt(rsc.vaultKey(VAULT_CHAIN, foreign)), 0);
    }

    function test_react_duplicateWithdrawal_countedOnce() public {
        vm.prank(system);
        rsc.react(_withdrawalLog(1, address(vault)));
        vm.prank(system);
        rsc.react(_withdrawalLog(1, address(vault))); // duplicate delivery
        vm.prank(system);
        rsc.react(_withdrawalLog(1, address(vault))); // and again
        assertEq(rsc.paceCount(), 1);
    }
}
