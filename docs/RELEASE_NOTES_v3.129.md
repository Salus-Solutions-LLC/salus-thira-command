# SalCAPA v3.129

## Protection Advisor embedded scroll reset

- Resets the embedded Protection Advisor document to its own top after the anonymous assessment starts.
- Resets the embedded document after every Previous or Next question transition.
- Prevents later questions from opening clipped above the visible Wix iframe.
- Preserves the bounded one-question-at-a-time flow introduced in v3.128.
- Makes no change to identity, authorization, retention, consent, or tenant boundaries.

## Validation

The focused public Protection Advisor smoke gate requires the scroll-reset behavior and rejects the earlier assessment-level smooth-scroll behavior.
