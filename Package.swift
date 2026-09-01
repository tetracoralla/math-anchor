// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "MathAnchor",
    platforms: [.macOS(.v14)],
    products: [
        .library(name: "MathAnchorCore", targets: ["MathAnchorCore"]),
        .executable(name: "MathAnchor", targets: ["MathAnchor"]),
    ],
    targets: [
        .target(
            name: "MathAnchorCore",
            path: "Sources/MathAnchorCore"
        ),
        .executableTarget(
            name: "MathAnchor",
            dependencies: ["MathAnchorCore"],
            path: "Sources/MathAnchor"
        ),
        .testTarget(
            name: "MathAnchorCoreTests",
            dependencies: ["MathAnchorCore"],
            path: "tests/MathAnchorCoreTests"
        ),
    ]
)
