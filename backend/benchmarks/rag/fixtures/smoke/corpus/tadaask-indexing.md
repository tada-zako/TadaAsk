# TadaAsk Indexing Lifecycle

New source items begin in the `pending` state. Indexing parses the document, splits it into chunks, creates embeddings, and writes the searchable records.

## Visibility rule

Only items whose status is completed are eligible for RAG retrieval. Pending, processing, paused, and failed items remain outside the visitor search scope.
