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

    VerdictRegistry registry;
    GuardedVault vault;
    SentinelReactive rsc;

    function setUp() public {
        SystemStub stub = new SystemStub();
        vm.etch(system, address(stub).code);
        registry = new VerdictRegistry(owner, writer);
        rsc = new SentinelReactive(address(registry));
        vault = new GuardedVault(owner, proxy, address(rsc));
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

    function test_freeze_wrongSenderFails() public {
        vm.prank(proxy);
        vm.expectRevert();
        vault.freeze(attacker, bytes32("HIGH_VERDICT"));
    }

    function test_react_onlySystem() public {
        LogRecord memory log_;
        log_.topic0 = uint256(keccak256("VerdictPosted(uint256,address,uint8,uint256,bytes32,bytes32)"));
        log_.topic1 = 7;
        log_.data = abi.encode(uint8(2), uint256(900), bytes32(0), bytes32(0));
        vm.prank(attacker);
        vm.expectRevert();
        rsc.react(log_);
    }
}
