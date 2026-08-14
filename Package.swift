// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "Zibetha",
    platforms: [.macOS(.v14)],
    products: [
        .executable(name: "Zibetha", targets: ["Zibetha"]),
    ],
    targets: [
        .executableTarget(
            name: "Zibetha",
            path: "Sources/Zibetha"
        ),
    ]
)
