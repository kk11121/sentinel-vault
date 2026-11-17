// SPDX-License-Identifier: MIT
pragma solidity ^0.8.29;

import { OmniReactive } from "../base/OmniReactive.sol";
import { LogRecord } from "../interfaces/IReactive.sol";

contract PingSource {
    event Ping(uint256 n);
    function ping(uint256 n) external {
        emit Ping(n);
    }
}

/// @notice Diagnostic: Lasna-local subscription -> react() state change.
contract PingReactive is OmniReactive {
    uint256 public count;
    uint256 public lastN;
    uint256 internal pingTopic0;

    constructor(address source_) payable {
        pingTopic0 = uint256(keccak256("Ping(uint256)"));
        SYSTEM.subscribe(block.chainid, source_, pingTopic0, REACTIVE_IGNORE, REACTIVE_IGNORE, REACTIVE_IGNORE);
    }

    function react(LogRecord memory log_) external override onlySystem {
        if (log_.topic0 != pingTopic0) return;
        count++;
        lastN = abi.decode(log_.data, (uint256));
    }
}
