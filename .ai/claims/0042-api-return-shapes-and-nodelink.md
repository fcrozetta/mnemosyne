# Claim 0042: API Return Shapes and Node-Link Standard

## Statement

The API supports two output shapes: raw document JSON and standardized node-link
for graph/path visualization.

## Return Shapes

- Document shape:
  - Return the Arango JSON document as-is for now.
- Graph/path shape:
  - Return standardized node-link format.

## Rules

- Write endpoints may return raw document JSON in v0.
- Path/query/visualization responses should standardize on node-link format.
- Deployment should install a UDF for path transformation, targeted as
  `MNEMOS::NODELINK(p)`.

## Acceptance Checks

- Response contracts distinguish document and graph/path outputs.
- Node-link shape is the standard for graph-oriented responses.
