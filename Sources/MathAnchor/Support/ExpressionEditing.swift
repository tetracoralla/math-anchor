import Foundation

struct TrailingOperand {
    let left: String?
    let operatorToken: String?
    let operand: String
}

enum ExpressionEditing {
    static func normalizedForRuntime(_ expression: String) -> String {
        expression
            .replacingOccurrences(of: "×", with: "*")
            .replacingOccurrences(of: "÷", with: "/")
            .replacingOccurrences(of: "−", with: "-")
    }

    static func evaluationExpression(forVisible expression: String) -> String {
        guard !expression.isEmpty else { return "" }
        if expression.hasSuffix("%") {
            let withoutPercent = String(expression.dropLast())
            guard let split = trailingOperand(in: withoutPercent) else {
                return normalizedForRuntime(withoutPercent) + "/100"
            }
            let operand = evaluationExpression(forVisible: split.operand)
            guard let left = split.left, let operatorToken = split.operatorToken else {
                return "(\(operand))/100"
            }
            let normalizedLeft = evaluationExpression(forVisible: left)
            let normalizedOperator = normalizedOperator(operatorToken)
            if normalizedOperator == "+" || normalizedOperator == "-" {
                return normalizedLeft
                    + normalizedOperator
                    + "((\(normalizedLeft))*(\(operand))/100)"
            }
            return normalizedLeft + normalizedOperator + "((\(operand))/100)"
        }

        guard let split = trailingOperand(in: expression),
              let left = split.left,
              let operatorToken = split.operatorToken
        else {
            return normalizedForRuntime(expression)
        }
        return evaluationExpression(forVisible: left)
            + normalizedOperator(operatorToken)
            + evaluationExpression(forVisible: split.operand)
    }

    static func togglingSign(in expression: String) -> String? {
        guard let split = trailingOperand(in: expression) else { return nil }
        let operatorToken = split.operatorToken.map(normalizedOperator)

        if let left = split.left, operatorToken == "+" {
            return left + "-" + split.operand
        }
        if let left = split.left, operatorToken == "-" {
            return left + "+" + split.operand
        }

        let toggledOperand: String
        if let positive = removingUnaryMinus(from: split.operand) {
            toggledOperand = positive
        } else {
            toggledOperand = "-" + split.operand
        }
        return replacingTrailingOperand(in: expression, with: toggledOperand)
    }

    static func trailingOperand(in expression: String) -> TrailingOperand? {
        guard !expression.isEmpty else { return nil }
        var depth = 0
        var lastOperatorRange: Range<String.Index>?
        var lastOperatorToken: String?
        var index = expression.startIndex

        while index < expression.endIndex {
            let character = expression[index]
            if character == "(" {
                depth += 1
                index = expression.index(after: index)
                continue
            }
            if character == ")" {
                depth = max(0, depth - 1)
                index = expression.index(after: index)
                continue
            }
            guard depth == 0 else {
                index = expression.index(after: index)
                continue
            }

            if character == "*" {
                let next = expression.index(after: index)
                if next < expression.endIndex, expression[next] == "*" {
                    let end = expression.index(after: next)
                    if isBinaryOperator(at: index, endingAt: end, in: expression) {
                        lastOperatorRange = index..<end
                        lastOperatorToken = "**"
                    }
                    index = end
                    continue
                }
            }

            if "+-−*/^×÷".contains(character) {
                let end = expression.index(after: index)
                if isBinaryOperator(at: index, endingAt: end, in: expression) {
                    lastOperatorRange = index..<end
                    lastOperatorToken = String(character)
                }
            }
            index = expression.index(after: index)
        }

        guard let range = lastOperatorRange, let operatorToken = lastOperatorToken else {
            return TrailingOperand(left: nil, operatorToken: nil, operand: expression)
        }
        let operandStart = range.upperBound
        guard operandStart < expression.endIndex else { return nil }
        return TrailingOperand(
            left: String(expression[..<range.lowerBound]),
            operatorToken: operatorToken,
            operand: String(expression[operandStart...])
        )
    }

    static func replacingTrailingOperand(in expression: String, with replacement: String) -> String? {
        guard let split = trailingOperand(in: expression) else { return nil }
        guard let left = split.left, let operatorToken = split.operatorToken else {
            return replacement
        }
        return left + operatorToken + replacement
    }

    private static func isBinaryOperator(
        at start: String.Index,
        endingAt end: String.Index,
        in expression: String
    ) -> Bool {
        guard let previous = previousNonWhitespace(before: start, in: expression),
              nextNonWhitespace(atOrAfter: end, in: expression) != nil
        else {
            return false
        }
        let previousCharacter = expression[previous]
        if "+-−*/^×÷(".contains(previousCharacter) {
            return false
        }
        let character = expression[start]
        if (character == "+" || character == "-") && isScientificNotationSign(at: start, in: expression) {
            return false
        }
        return true
    }

    private static func normalizedOperator(_ token: String) -> String {
        switch token {
        case "×": "*"
        case "÷": "/"
        case "−": "-"
        default: token
        }
    }

    private static func removingUnaryMinus(from operand: String) -> String? {
        if operand.hasPrefix("-("), operand.hasSuffix(")") {
            return String(operand.dropFirst(2).dropLast())
        }
        if operand.hasPrefix("−(") && operand.hasSuffix(")") {
            return String(operand.dropFirst(2).dropLast())
        }
        if operand.hasPrefix("-") || operand.hasPrefix("−") {
            return String(operand.dropFirst())
        }
        return nil
    }

    private static func isScientificNotationSign(at index: String.Index, in expression: String) -> Bool {
        guard let exponentMarker = previousNonWhitespace(before: index, in: expression),
              expression[exponentMarker] == "e" || expression[exponentMarker] == "E",
              let numberCharacter = previousNonWhitespace(before: exponentMarker, in: expression)
        else {
            return false
        }
        return expression[numberCharacter].isNumber || expression[numberCharacter] == "."
    }

    private static func previousNonWhitespace(
        before index: String.Index,
        in expression: String
    ) -> String.Index? {
        var candidate = index
        while candidate > expression.startIndex {
            candidate = expression.index(before: candidate)
            if !expression[candidate].isWhitespace { return candidate }
        }
        return nil
    }

    private static func nextNonWhitespace(
        atOrAfter index: String.Index,
        in expression: String
    ) -> String.Index? {
        var candidate = index
        while candidate < expression.endIndex {
            if !expression[candidate].isWhitespace { return candidate }
            candidate = expression.index(after: candidate)
        }
        return nil
    }
}
