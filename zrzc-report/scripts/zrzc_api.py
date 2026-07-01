#!/usr/bin/env python3
"""影响范围评估 API 客户端 - 提交分析请求、轮询结果、查询 TAPD 标题"""

import argparse
import json
import sys
import time
import urllib.request
import urllib.error


def build_headers(swim_lane_id: str = "") -> dict:
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    if swim_lane_id:
        headers["fintopia-swim-lane-id"] = swim_lane_id
    return headers


def api_request(url: str, data: dict = None, headers: dict = None, method: str = None) -> dict:
    """Send HTTP request and return parsed JSON."""
    body = json.dumps(data).encode("utf-8") if data else None
    req = urllib.request.Request(url, data=body, headers=headers or {}, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8", errors="replace")
        return {"error": True, "status_code": e.code, "detail": error_body}
    except urllib.error.URLError as e:
        return {"error": True, "detail": str(e.reason)}
    except Exception as e:
        return {"error": True, "detail": str(e)}


def cmd_analyze(args):
    """Submit an analysis request and print task_id."""
    url = f"{args.api_base.rstrip('/')}/api/analyze"
    payload = {
        "repo": args.repo,
        "branch": args.branch,
        "base_branch": args.base_branch,
        "title": args.title or None,
        "tapd_link": args.tapd_link or None,
        "requirement_doc": None,
        "upload_to_feishu": args.upload_to_feishu.lower() == "true",
        "send_notify": args.send_notify.lower() == "true",
        "parallel": args.parallel.lower() == "true",
    }
    headers = build_headers(args.swim_lane_id)
    result = api_request(url, data=payload, headers=headers)
    print(json.dumps(result, ensure_ascii=False, indent=2))


def cmd_poll(args):
    """Poll task status until completion or timeout."""
    base = args.api_base.rstrip("/")
    url = f"{base}/api/task/{args.task_id}"
    headers = build_headers(args.swim_lane_id)

    max_wait = 600  # 10 minutes
    interval = 5
    elapsed = 0

    while elapsed < max_wait:
        result = api_request(url, headers=headers, method="GET")
        if result.get("error"):
            print(json.dumps(result, ensure_ascii=False, indent=2))
            sys.exit(1)

        status = result.get("status", "")
        progress = result.get("progress", "")

        if status in ("completed", "failed"):
            print(json.dumps(result, ensure_ascii=False, indent=2))
            sys.exit(0 if status == "completed" else 1)

        print(f"[{elapsed}s] 状态: {status} | 进度: {progress}", file=sys.stderr)
        time.sleep(interval)
        elapsed += interval

    print(json.dumps({"error": True, "detail": f"轮询超时 ({max_wait}s)"}, ensure_ascii=False, indent=2))
    sys.exit(1)


def cmd_tapd_title(args):
    """Query TAPD story title via the zrzc API."""
    url = f"{args.api_base.rstrip('/')}/api/tapd/story"
    params = urllib.parse.urlencode({"tapd_link": args.tapd_link})
    full_url = f"{url}?{params}"
    headers = build_headers(args.swim_lane_id)
    result = api_request(full_url, headers=headers, method="GET")
    print(json.dumps(result, ensure_ascii=False, indent=2))


def cmd_task_status(args):
    """Check task status once (no polling)."""
    url = f"{args.api_base.rstrip('/')}/api/task/{args.task_id}"
    headers = build_headers(args.swim_lane_id)
    result = api_request(url, headers=headers, method="GET")
    print(json.dumps(result, ensure_ascii=False, indent=2))


def main():
    import urllib.parse

    parser = argparse.ArgumentParser(description="影响范围评估 API 客户端")
    sub = parser.add_subparsers(dest="command")

    # analyze
    p_analyze = sub.add_parser("analyze", help="提交分析请求")
    p_analyze.add_argument("--api-base", required=True)
    p_analyze.add_argument("--repo", required=True)
    p_analyze.add_argument("--branch", required=True)
    p_analyze.add_argument("--base-branch", default="master")
    p_analyze.add_argument("--title", default="")
    p_analyze.add_argument("--tapd-link", default="")
    p_analyze.add_argument("--upload-to-feishu", default="false")
    p_analyze.add_argument("--send-notify", default="false")
    p_analyze.add_argument("--parallel", default="true")
    p_analyze.add_argument("--swim-lane-id", default="")

    # poll
    p_poll = sub.add_parser("poll", help="轮询任务状态")
    p_poll.add_argument("--api-base", required=True)
    p_poll.add_argument("--task-id", required=True)
    p_poll.add_argument("--swim-lane-id", default="")

    # tapd-title
    p_tapd = sub.add_parser("tapd-title", help="查询 TAPD 需求标题")
    p_tapd.add_argument("--api-base", required=True)
    p_tapd.add_argument("--tapd-link", required=True)
    p_tapd.add_argument("--swim-lane-id", default="")

    # task-status
    p_status = sub.add_parser("task-status", help="查询任务状态（单次）")
    p_status.add_argument("--api-base", required=True)
    p_status.add_argument("--task-id", required=True)
    p_status.add_argument("--swim-lane-id", default="")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    dispatch = {
        "analyze": cmd_analyze,
        "poll": cmd_poll,
        "tapd-title": cmd_tapd_title,
        "task-status": cmd_task_status,
    }
    dispatch[args.command](args)


if __name__ == "__main__":
    main()
