# V4 Template Contract

V4 renders section keys in this fixed order and localizes titles to Chinese or
English based on upstream `language`:

- conclusion -> 结论 / Conclusion
- engineering_meaning -> 工程意义 / Engineering Meaning
- premises -> 适用前提 / Premises
- failure_modes -> 失效条件/常见误区 / Failure Conditions / Common Pitfalls
- minimal_model -> 最简模型/公式 / Minimal Model / Formula
- next_action -> 下一步建议 / Next Actions
- evidence -> 证据 / Evidence

Only sections with non-empty upstream content are rendered. Phase-0 normally
renders conclusion plus evidence because S3 does not yet produce engineering
analysis subsections.