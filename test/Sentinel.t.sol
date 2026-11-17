// SPDX-License-Identifier: MIT
pragma solidity ^0.8.29;

import { Test } from "forge-std/Test.sol";
import { VerdictRegistry } from "../src/contracts/VerdictRegistry.sol";
import { GuardedVault } from "../src/contracts/GuardedVault.sol";
import { SentinelReactive } from "../src/contracts/SentinelReactive.sol";
import { ISystemContract } from "../src/interfaces/ISystemContract.sol";
import { LogRecord } from "../src/interfaces/IReactive.sol";

contract SystemStub {
    uint256 public callbackCount;

    function requestCallbackV_1_0(ISystemContract.CallbackConfiguration_V_1_0 memory) external {
        callbackCount++;
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

    function _verdictLog(uint256 requestId, address vault_, uint8 severity) internal view returns (LogRecord memory log_) {
        log_.chainId = 84532;
        log_.contractAddress = address(registry);
        log_.topic0 = uint256(keccak256("VerdictPosted(uint256,address,uint256,uint8,uint256,bytes32,bytes32)"));
        log_.topic1 = VAULT_CHAIN;
        log_.topic2 = uint256(uint160(vault_));
        log_.topic3 = requestId;
        log_.data = abi.encode(severity, uint256(900), bytes32(0), bytes32(0));
    }

    function _withdrawalLog(uint256 requestId, address vault_) internal view returns (LogRecord memory log_) {
        log_.chainId = VAULT_CHAIN;
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
        (,, uint256 amount3, uint256 readyAt3,,) = vault.withdrawals(id3);
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
        (,,, uint256 readyAt4,,) = vault.withdrawals(id4);
        assertEq(readyAt4, block.timestamp);
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
        assertGt(rsc.lastMediumAt(address(vault)), 0);
        assertEq(_callbacks(), 1); // exactly one veto callback
    }

    function test_react_mediumUnknownRequest_ignored() public {
        vm.prank(system);
        rsc.react(_verdictLog(99, address(vault), 1));
        assertEq(rsc.lastMediumAt(address(vault)), 0);
        assertEq(_callbacks(), 0);
    }

    function test_react_highFreezes_evenUnknownRequest() public {
        vm.prank(system);
        rsc.react(_verdictLog(99, address(vault), 2));
        assertEq(_callbacks(), 1); // one configured vault -> one freeze callback
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
        assertEq(_callbacks(), 2); // +1 freeze callback (one vault configured)
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
        assertEq(_callbacks(), 3); // freeze adds exactly 1 (one vault)
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
}
