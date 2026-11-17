// SPDX-License-Identifier: MIT
pragma solidity ^0.8.29;

import { Test } from "forge-std/Test.sol";
import { VerdictRegistry } from "../src/contracts/VerdictRegistry.sol";
import { GuardedVault } from "../src/contracts/GuardedVault.sol";
import { SentinelReactive } from "../src/contracts/SentinelReactive.sol";
import { LogRecord } from "../src/interfaces/IReactive.sol";

contract SystemStub {
    fallback() external payable { }
    function debts(address) external pure returns (uint256) {
        return 0;
    }
}

contract SentinelTest is Test {
    address owner = address(0xA11CE);
    address writer = address(0xB0B);
    address attacker = address(0xBAD);
    address proxy = address(0xCA11BAC);
    address system = 0x8888888888888888888888888888888888888888;
    address user = address(0x555E12);

    VerdictRegistry registry;
    GuardedVault vault;
    SentinelReactive rsc;

    function setUp() public {
        SystemStub stub = new SystemStub();
        vm.etch(system, address(stub).code);
        registry = new VerdictRegistry(owner, writer);
        rsc = new SentinelReactive(address(registry));
        vault = new GuardedVault(owner, proxy, address(rsc), 600, 0.02 ether);
        vm.deal(address(vault), 1 ether);
        rsc.setVault(11155111, address(vault));
    }

    function _verdictLog(uint256 requestId, address vault_, uint8 severity) internal pure returns (LogRecord memory log_) {
        log_.topic0 = uint256(keccak256("VerdictPosted(uint256,address,uint8,uint256,bytes32,bytes32)"));
        log_.topic1 = requestId;
        log_.topic2 = uint256(uint160(vault_));
        log_.data = abi.encode(severity, uint256(900), bytes32(0), bytes32(0));
    }

    function test_postVerdict_onlyWriter() public {
        vm.prank(attacker);
        vm.expectRevert(VerdictRegistry.NotVerdictWriter.selector);
        registry.postVerdict(1, address(vault), 2, 900, bytes32(0), bytes32(0));
        vm.prank(writer);
        registry.postVerdict(1, address(vault), 2, 900, bytes32(0), bytes32(0));
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

    function test_largeWithdrawal_waitsThenExecutes() public {
        vm.prank(user);
        uint256 id = vault.requestWithdrawal(user, 0.05 ether);
        vm.expectRevert(GuardedVault.NotReady.selector);
        vault.executeWithdrawal(id);
        vm.warp(block.timestamp + 601);
        uint256 before = user.balance;
        vault.executeWithdrawal(id);
        assertEq(user.balance - before, 0.05 ether);
    }

    function test_smallWithdrawal_immediate() public {
        vm.prank(user);
        uint256 id = vault.requestWithdrawal(user, 0.001 ether);
        uint256 before = user.balance;
        vault.executeWithdrawal(id);
        assertEq(user.balance - before, 0.001 ether);
    }

    function test_veto_blocksExecution() public {
        vm.prank(user);
        uint256 id = vault.requestWithdrawal(attacker, 0.05 ether);
        vm.prank(proxy);
        vault.veto(address(rsc), id);
        vm.warp(block.timestamp + 601);
        vm.expectRevert(GuardedVault.Vetoed.selector);
        vault.executeWithdrawal(id);
    }

    function test_veto_directCallFails() public {
        vm.prank(user);
        uint256 id = vault.requestWithdrawal(attacker, 0.05 ether);
        vm.prank(attacker);
        vm.expectRevert();
        vault.veto(address(rsc), id);
    }

    function test_frozen_blocksWithdrawals() public {
        vm.prank(proxy);
        vault.freeze(address(rsc), bytes32("HIGH_VERDICT"));
        vm.prank(user);
        vm.expectRevert(GuardedVault.VaultFrozen.selector);
        vault.requestWithdrawal(user, 0.001 ether);
    }

    function test_react_onlySystem() public {
        vm.prank(attacker);
        vm.expectRevert();
        rsc.react(_verdictLog(7, address(vault), 2));
    }

    function test_react_mediumRecordsTimestamp() public {
        vm.prank(system);
        rsc.react(_verdictLog(1, address(vault), 1));
        assertGt(rsc.lastMediumAt(address(vault)), 0);
    }
}
