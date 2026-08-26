import Foundation

package struct TrailingOperand {
    package let left: String?
    package let operatorToken: String?
    package let operand: String
}

package enum ExpressionEditing {
    package static func normalizedForRuntime(_ expression: String) -> String {
        expression
            // Re-derivation after backspace or a unary edit must preserve the
            // keypad's familiar base-10 `log` meaning even while its call is
            // still open and therefore cannot be parsed as a closed operand.
            .replacingOccurrences(of: "log(", with: "log10(")
            .replacingOccurrences(of: "×", with: "*")
            .replacingOccurrences(of: "÷", with: "/")
            .replacingOccurrences(of: "−", with: "-")
    }

    package static func evaluationExpression(forVisible expression: String) -> String {
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
            return translatedOperand(expression)
        }
        return evaluationExpression(forVisible: left)
            + normalizedOperator(operatorToken)
            + evaluationExpression(forVisible: split.operand)
    }

    /// The familiar `log` key means base 10; the core's `log` name is natural
    /// log, so the executable form uses the explicit base-10 name.
    package static func runtimeFunctionName(_ name: String) -> String {
        name == "log" ? "log10" : name
    }

    /// Translates a trailing operand that carries no top-level operator.
    /// Closed groups and named calls descend so percent notation anywhere in
    /// the visible expression reaches its executable expansion.
    private static func translatedOperand(_ operand: String) -> String {
        if let inner = closedGroupInner(operand) {
            return "(" + evaluationExpression(forVisible: inner) + ")"
        }
        if let call = namedCall(operand) {
            return runtimeFunctionName(call.name)
                + "("
                + evaluationExpression(forVisible: call.argument)
                + ")"
        }
        return normalizedForRuntime(operand)
    }

    /// Content of a leading group whose parenthesis matches the operand's
    /// final character; still-open or trailing groups stay opaque.
    private static func closedGroupInner(_ operand: String) -> String? {
        guard operand.hasPrefix("("), operand.hasSuffix(")") else { return nil }
        var depth = 0
        for index in operand.indices {
            if operand[index] == "(" {
                depth += 1
            } else if operand[index] == ")" {
                depth -= 1
                if depth == 0 {
                    guard index == operand.index(before: operand.endIndex) else { return nil }
                    return String(operand[operand.index(after: operand.startIndex)..<index])
                }
            }
        }
        return nil
    }

    /// A named call such as `sin(50%)` whose parenthesis matches the operand's
    /// final character. Still-open arguments fall through to lexical runtime
    /// normalization, which preserves their structure while translating the
    /// keypad's `log(` alias.
    private static func namedCall(_ operand: String) -> (name: String, argument: String)? {
        guard let openingIndex = operand.firstIndex(of: "("), operand.hasSuffix(")") else {
            return nil
        }
        let name = String(operand[..<openingIndex])
        guard name.first?.isLetter == true,
              name.allSatisfy({ $0.isLetter || $0.isNumber })
        else { return nil }
        var depth = 0
        for index in operand.indices {
            if operand[index] == "(" {
                depth += 1
            } else if operand[index] == ")" {
                depth -= 1
                if depth == 0 {
                    guard index == operand.index(before: operand.endIndex) else { return nil }
                    return (
                        name,
                        String(operand[operand.index(after: openingIndex)..<index])
                    )
                }
            }
        }
        return nil
    }

    package static func togglingSign(in expression: String) -> String? {
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

    package static func trailingOperand(in expression: String) -> TrailingOperand? {
        guard !expression.isEmpty else { return nil }
        // Operator binding stops at the innermost still-open group, so edits
        // inside "(5+3" address the pending `3` exactly as they would at the
        // top level instead of swallowing the whole open parenthetical.
        let scanStart = innermostGroupStart(in: expression)
        var depth = 0
        var lastOperatorRange: Range<String.Index>?
        var lastOperatorToken: String?
        var index = scanStart

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

    package static func replacingTrailingOperand(in expression: String, with replacement: String) -> String? {
        guard let split = trailingOperand(in: expression) else { return nil }
        guard let left = split.left, let operatorToken = split.operatorToken else {
            return replacement
        }
        return left + operatorToken + replacement
    }

    /// Index just past the last "(" with no matching ")". Scanning backward,
    /// the first "(" that nothing closes is the innermost still-open group.
    private static func innermostGroupStart(in expression: String) -> String.Index {
        var depthFromEnd = 0
        var index = expression.endIndex
        while index > expression.startIndex {
            index = expression.index(before: index)
            let character = expression[index]
            if character == ")" {
                depthFromEnd += 1
            } else if character == "(" {
                if depthFromEnd > 0 {
                    depthFromEnd -= 1
                } else {
                    return expression.index(after: index)
                }
            }
        }
        return expression.startIndex
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
