# CS Health mock API

Simulates a paginated REST endpoint. Start at `cursor_01.json`. Each response has
`results` and `next_cursor`; follow `next_cursor` until it is null. Treat each file
as one HTTP GET. A response containing `error` is a failed call — honour
`retry_after_seconds` and re-request the URL in `retry_url`.

Records are keyed by `snapshot_id`.
