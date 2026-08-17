// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "MathAnchor",
    platforms: [.macOS(.v14)],
    products: [
        .executable(name: "MathAnchor", targets: ["MathAnchor"]),
    ],
    targets: [
        .executableTarget(
            name: "MathAnchor",
            path: "Sources/MathAnchor"
        ),
    ]
)
