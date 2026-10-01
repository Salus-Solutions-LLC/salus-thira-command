.answers as $answers
| ($answers | length) == $expected
  and ([$before[0] | to_entries[] | select($answers[.key] != .value)] | length) == 0
