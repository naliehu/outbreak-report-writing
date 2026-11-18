/**
 * outbreak-report-writing —— DSH 插件：把流调报告流水线暴露成 epi_report 工具。
 *
 * 设计取舍
 *  - 不重写生成逻辑：报告怎么写、画什么图、缺项怎么分级，全在技能目录的 Python 里，
 *    插件只做「找目录 → 选解释器 → 传参 → 回收产物路径」。一处真源，两种外壳。
 *  - 缺依赖不报错：没装 matplotlib 就出文字稿并说明原因；没装 python-docx 就只给 md。
 *  - 一律返回绝对路径，模型不必猜产物在哪。
 */
import { execFile } from 'node:child_process'
import { existsSync, readdirSync } from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { defineTool } from '@deepseek-ai/dsh-tools'

export const name = 'epi-report'
export const inject = ['tools']

const PKG_DIR = path.dirname(fileURLToPath(import.meta.url))
const BUILD = 'scripts/build_report.py'

/** dsh 工具的统一输出外壳：{ok, result}，result 进对话正文。 */
const OUT = () => ({
  schema: {
    type: 'object',
    additionalProperties: false,
    properties: {
      ok: { type: 'boolean', required: true },
      result: { type: 'string', required: true },
    },
  },
  render: (_args, value) => [{ type: 'text', text: value.result }],
})

const ok = (result) => ({ ok: true, result })
const fail = (result) => ({ ok: false, result })

/** 依次尝试：配置显式指定 → 本机技能目录 → 本包自带副本。 */
function resolveSkillDir(config) {
  const candidates = [
    config?.skillDir,
    path.join(os.homedir(), '.hermes', 'skills', 'outbreak-report-writing'),
    PKG_DIR,
  ].filter(Boolean)
  for (const dir of candidates) {
    if (existsSync(path.join(dir, BUILD))) return dir
  }
  return PKG_DIR
}

/** 解释器：配置 → vendor/venv → python3。 */
function resolvePython(skillDir, config) {
  const candidates = [
    config?.python,
    path.join(skillDir, 'vendor', 'venv', 'bin', 'python'),
    'python3',
  ].filter(Boolean)
  for (const py of candidates) {
    if (py === 'python3' || existsSync(py)) return py
  }
  return 'python3'
}

function run(cmd, args, cwd, timeoutMs = 900_000) {
  return new Promise((resolve) => {
    execFile(cmd, args, { cwd, timeout: timeoutMs, maxBuffer: 8 * 1024 * 1024, env: cleanEnv() },
      (err, stdout, stderr) => resolve({ err, stdout: stdout || '', stderr: stderr || '' }))
  })
}

/** 清掉可能污染子进程的 Python 环境变量（venv 自带的 PYTHONPATH 常导致 import 失败）。 */
function cleanEnv() {
  const env = { ...process.env }
  delete env.PYTHONPATH
  delete env.VIRTUAL_ENV
  delete env.PYTHONHOME
  return env
}

function listOutputs(dir) {
  try {
    return readdirSync(dir).filter((f) => /\.(md|docx|pdf)$/i.test(f)).map((f) => path.join(dir, f))
  } catch {
    return []
  }
}

export function apply(ctx, config = {}) {
  const skillDir = resolveSkillDir(config)
  const python = resolvePython(skillDir, config)
  ctx.logger?.info?.(`[epi-report] skill=${skillDir} python=${python}`)

  ctx.tools.register(defineTool({
    name: 'epi_report',
    description:
      '生成传染病现场流行病学调查报告（流调报告）。输入一份事件描述文件（YAML/JSON，最少五个字段：'
      + '病种、机构、首例发病日期、病例数、一条已采取措施），可再给一份大疫情网导出的个案 CSV，'
      + '输出 markdown / docx / pdf，并按病种自动配流行曲线、班级分布、年龄性别、代际、传播链等图。'
      + '信息不全也出稿：缺的字段在正文渲染为〔待补P0-2〕，附录 A 按 P0（阻断传播，24 小时内）／'
      + 'P1（影响研判，48 小时内）／P2（完善叙述，结案前）排序并写明还差什么。'
      + 'action=check 只做输入体检、不出稿，适合先看还缺什么。',
    parameters: {
      action: {
        type: 'string',
        enum: ['build', 'check'],
        description: 'build=出稿（默认）；check=只体检缺项与完成度，不写文件。',
      },
      event_path: {
        type: 'string',
        required: true,
        description: '事件 YAML/JSON 的路径（绝对路径，或相对当前工作目录）。',
      },
      stage: {
        type: 'string',
        enum: ['initial', 'progress', 'final', 'closure', 'case'],
        description: 'initial=初次/初步调查报告（默认）；progress=进程报告；final=结案调查报告；'
          + 'closure=结案申请单（报市疾控一页纸）；case=单例病例流调报告。',
      },
      line_list: {
        type: 'string',
        description: '可选：大疫情网导出的个案 CSV 路径。有它才能画流行曲线、班级分布、年龄性别、代际。',
      },
      out_dir: {
        type: 'string',
        description: '可选：输出目录，缺省为事件文件同级的「流调输出」。',
      },
      formats: {
        type: 'string',
        description: '可选：逗号分隔的导出格式，默认 md,docx,pdf。缺 python-docx 时 docx/pdf 会跳过并说明。',
      },
      docx_profile: {
        type: 'string',
        enum: ['default', 'gongwen', 'compact'],
        description: 'Word 版式：default=宋体小四 1.5 倍行距（默认）；gongwen=仿宋三号公文版；compact=紧凑。',
      },
    },
    output: OUT(),
    execute: async (args = {}) => {
      const eventPath = String(args.event_path || '').trim()
      if (!eventPath) return fail('缺少 event_path：请给出事件 YAML/JSON 的路径。')
      if (!existsSync(eventPath)) return fail(`找不到事件文件：${eventPath}`)

      const argv = [path.join(skillDir, BUILD), '--event', eventPath]
      if (args.action === 'check') {
        argv.push('--check')
      } else {
        const outDir = args.out_dir || config?.outDir
          || path.join(path.dirname(path.resolve(eventPath)), '流调输出')
        argv.push(
          '--out', outDir,
          '--stage', args.stage || 'initial',
          '--formats', args.formats || 'md,docx,pdf',
          '--docx-profile', args.docx_profile || 'default',
        )
        if (args.line_list) argv.push('--line-list', args.line_list)
      }

      const { err, stdout, stderr } = await run(python, argv, skillDir)

      let payload
      try {
        payload = JSON.parse(stdout.trim())
      } catch {
        payload = { stdout: stdout.trim().slice(-2000) }
      }
      if (err) {
        payload.error = `生成失败（exit ${err.code ?? '?'}）`
        payload.hint = '先跑 action=check 看输入体检结果；或确认 python3 已装 pyyaml、jinja2、'
          + 'python-docx、matplotlib 四项依赖。'
        payload.stderr = stderr.trim().slice(-1500)
        return fail(JSON.stringify(payload, null, 2))
      }
      if (payload.outputs && payload.outputs.md) {
        payload.files = listOutputs(path.dirname(payload.outputs.md))
        payload.next = '缺项清单在文末附录 A；P0 项补齐后重跑同一条命令即可覆盖输出。'
      }
      return ok(JSON.stringify(payload, null, 2))
    },
  }))
}
