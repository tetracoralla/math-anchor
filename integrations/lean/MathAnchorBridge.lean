import Mathlib.Tactic

/-!
Math Anchor generates bounded theorem artifacts at check time. This library
pins the Mathlib dependency and ensures the `ring` proof producer is available;
Lean's kernel still checks every generated proof term.
-/

namespace MathAnchorBridge

theorem smoke (x y : ℚ) : (x + y) ^ 2 = x ^ 2 + 2 * x * y + y ^ 2 := by
  ring

end MathAnchorBridge
