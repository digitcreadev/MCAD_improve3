# R3-E14 D12 raw inference result freeze

This directory freezes the byte-exact outputs of the completed D11-A2
preregistered inference execution before any scientific interpretation.

Analysis id:
`r3e_e14_d11_a2_preregistered_inference_20260903T170933Z`

Parent Git authority:
`9c4168f65a5ec6f7a734aa9028916d8821f498c7`

Frozen source payloads include:
- exact D11-A2 wrapper
- exact D11-A2 analysis program
- measurement-integrity receipt
- raw inference results
- D11 state
- D11 console log
- D11 execution receipt
- published D11-A2 recovery authorization

Boundary:
- no measurement reexecution
- no result interpretation
- no claim reporting
- no cross-backend synthesis
- no Docker / HTTP / XMLA execution
- raw result values were not printed by D12
- D13 requires a separate authorization before any scientific result interpretation
