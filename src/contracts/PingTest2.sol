// SPDX-License-Identifier: MIT
pragma solidity ^0.8.29;

import { OmniReactive } from "../base/OmniReactive.sol";
import { LogRecord } from "../interfaces/IReactive.sol";

/// @notice Diagnostic v2: subscribe AFTER deployment via an external call,
///         mirroring the pattern seen in working on-chain subscriptions.
contract PingReactive2 is OmniReactive {
    uint256 public count;
    address public source;
    uint256 internal pingTopic0;

    constructor(address source_) payable {
        source = source_;
        pingTopic0 = uint256(keccak256("Ping(uint256)"));
    }

    function arm() external {
        SYSTEM.subscribe(block.chainid, source, pingTopic0, REACTIVE_IGNORE, REACTIVE_IGNORE, REACTIVE_IGNORE);
    }

    function react(LogRecord memory log_) external override onlySystem {
        if (log_.topic0 != pingTopic0) return;
        count++;
    }
}
