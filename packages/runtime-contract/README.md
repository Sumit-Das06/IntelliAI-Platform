# packages/runtime-contract — Internal Inference Contract

Pydantic schemas defining the internal request/response contract between the
gateway and inference services, organized per capability (transcription,
speech synthesis, …later: chat, embeddings). This contract is what makes models
and providers swappable without client-visible change. Arrives in Milestone 2.

Imports nothing internal. Deliberately tiny — no framework dependencies beyond
Pydantic.
