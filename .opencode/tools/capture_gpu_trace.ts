import { tool } from "@opencode-ai/plugin"

import { runPythonTool } from "./_shared"

export default tool({
  description: "Capture a representative Metal GPU trace",
  args: {
    trace_path: tool.schema
      .string()
      .default("state/batch_generate_profile.gputrace")
      .describe("Output .gputrace path relative to the repo root or absolute"),
    fixture_index: tool.schema
      .number()
      .int()
      .nonnegative()
      .default(0)
      .describe("Fixture index to use for the representative batch_generate call"),
  },
  async execute(args, context) {
    return runPythonTool(
      "capture_gpu_trace.py",
      [
        "--metal-profile-path",
        args.trace_path,
        "--metal-profile-fixture-index",
        String(args.fixture_index),
      ],
      { MTL_CAPTURE_ENABLED: "1" },
      context.worktree,
    )
  },
})
