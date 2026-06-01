// swift-tools-version: 6.0

import PackageDescription

let package = Package(
    name: "FraudMonitor",
    platforms: [
        .iOS(.v17),
        .macOS(.v14),
    ],
    products: [
        .executable(name: "FraudMonitorApp", targets: ["FraudMonitorApp"]),
        .executable(name: "FraudMonitorMac", targets: ["FraudMonitorMac"]),
        .library(name: "FraudMonitorCore", targets: ["FraudMonitorCore"]),
    ],
    targets: [
        .target(
            name: "FraudMonitorCore"
        ),
        .executableTarget(
            name: "FraudMonitorApp",
            dependencies: ["FraudMonitorCore"]
        ),
        .executableTarget(
            name: "FraudMonitorMac",
            dependencies: ["FraudMonitorCore"]
        ),
    ]
)
