import { spawn } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const serverDirectory = fileURLToPath(new URL('../', import.meta.url))
const pythonExecutable =
  process.platform === 'win32'
    ? path.join(serverDirectory, '.venv', 'Scripts', 'python.exe')
    : path.join(serverDirectory, '.venv', 'bin', 'python')

const server = spawn(
  pythonExecutable,
  ['-m', 'uvicorn', 'app.main:app', '--reload', '--port', '8000'],
  { cwd: serverDirectory, stdio: 'inherit' },
)

server.on('error', (error) => {
  console.error(`Unable to start the Yaad API using ${pythonExecutable}:`, error)
  process.exitCode = 1
})

server.on('exit', (code, signal) => {
  if (signal) {
    process.kill(process.pid, signal)
  } else {
    process.exitCode = code ?? 1
  }
})
