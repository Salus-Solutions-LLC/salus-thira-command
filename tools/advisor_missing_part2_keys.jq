. as $response | .questions[].key | select($response.answers[.] == null)
