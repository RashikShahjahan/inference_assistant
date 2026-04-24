import { tool } from "@opencode-ai/plugin"

import { runPythonTool } from "./_shared"

export default tool({
  description: "Export xctrace XML for a trace table schema",
  args: {
    trace_path: tool.schema
      .string()
      .default("state/batch_generate_profile.trace")
      .describe("Path to a .trace document, relative to repo root or absolute"),
    schema: tool.schema
      .string()
      .describe(
        "Trace table schema name, for example metal-gpu-intervals, metal-application-intervals, or metal-application-command-buffer-submissions",
      ),
    run_number: tool.schema
      .number()
      .int()
      .positive()
      .default(1)
      .describe("Trace run number to export from"),
  },
  async execute(args, context) {
    return runPythonTool(
      "trace_export_table.py",
      [
        "--trace-path",
        args.trace_path,
        "--schema",
        args.schema,
        "--run-number",
        String(args.run_number),
      ],
      {},
      context.worktree,
    )
  },
})
