import { spawn } from "node:child_process"
import path from "node:path"

import type { ToolResult } from "@opencode-ai/plugin/tool"

export async function runPythonTool(
  scriptName: string,
  args: string[],
  env: Record<string, string>,
  cwd: string,
): Promise<ToolResult> {
  const scriptPath = path.join(cwd, ".opencode/tools", scriptName)

  const proc = spawn("uv", ["run", "python3", scriptPath, ...args], {
    cwd,
    env: { ...process.env, ...env },
  })

  const stdoutPromise = new Promise<string>((resolve, reject) => {
    let stdout = ""
    proc.stdout?.setEncoding("utf8")
    proc.stdout?.on("data", (chunk: string) => {
      stdout += chunk
    })
    proc.stdout?.on("error", reject)
    proc.stdout?.on("end", () => {
      resolve(stdout)
    })
  })

  const stderrPromise = new Promise<string>((resolve, reject) => {
    let stderr = ""
    proc.stderr?.setEncoding("utf8")
    proc.stderr?.on("data", (chunk: string) => {
      stderr += chunk
    })
    proc.stderr?.on("error", reject)
    proc.stderr?.on("end", () => {
      resolve(stderr)
    })
  })

  const exitCodePromise = new Promise<number>((resolve, reject) => {
    proc.on("error", reject)
    proc.on("close", (code) => {
      resolve(code ?? 1)
    })
  })

  const [stdout, stderr, exitCode] = await Promise.all([
    stdoutPromise,
    stderrPromise,
    exitCodePromise,
  ])

  const trimmedStdout = stdout.trim()
  const trimmedStderr = stderr.trim()

  if (!trimmedStdout) {
    throw new Error(trimmedStderr || `${scriptName} exited with code ${exitCode}`)
  }

  let result: ToolResult
  try {
    result = JSON.parse(trimmedStdout) as ToolResult
  } catch (error) {
    throw new Error(
      `Failed to parse ${scriptName} output as JSON: ${error instanceof Error ? error.message : String(error)}\n${trimmedStdout}`,
    )
  }

  if (exitCode !== 0) {
    throw new Error(trimmedStderr || `${scriptName} exited with code ${exitCode}`)
  }

  return result
}
