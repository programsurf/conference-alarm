#!/usr/bin/env python3
"""
Conference Deadline Alert Bot v2
다중 소스에서 탑티어 학회 데드라인을 수집하여 Slack으로 알림
"""

import requests
import json
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
import os
import re

SLACK_WEBHOOK_URL = os.environ.get('SLACK_WEBHOOK_URL')

# 트래킹할 학회 목록 (소문자로 매칭용)
TARGET_CONFERENCES = {
    "AI/Vision": ["cvpr", "eccv", "iccv", "aaai", "icml", "iclr", "neurips", "nips"],
    "Security": ["ieee s&p", "sp", "oakland", "ccs", "usenix security", "ndss", "eurocrypt", "crypto", "esorics", "dsn"],
    "Network": ["sigmetrics", "infocom", "sigcomm", "nsdi", "imc"],
    "Data": ["icdm", "bigdata", "kdd", "vldb", "sigmod"],
}


def fetch_from_aideadlines():
    """aideadlin.es에서 AI 학회 데드라인 가져오기"""
    deadlines = []
    try:
        url = "https://aideadlin.es/data/deadlines.json"
        response = requests.get(url, timeout=15)
        if response.status_code == 200:
            data = response.json()
            for conf in data:
                deadlines.append({
                    "name": conf.get("name", ""),
                    "full_name": conf.get("full_name", ""),
                    "deadline": conf.get("deadline", ""),
                    "timezone": conf.get("timezone", "UTC"),
                    "link": conf.get("link", ""),
                    "place": conf.get("place", ""),
                    "source": "aideadlines"
                })
            print(f"[aideadlines] Fetched {len(deadlines)} conferences")
    except Exception as e:
        print(f"[aideadlines] Error: {e}")
    return deadlines


def fetch_from_ccfddl():
    """ccfddl (CCF Deadline) GitHub에서 데드라인 가져오기"""
    deadlines = []
    categories = ["AI", "security", "network", "database"]
    
    for cat in categories:
        try:
            url = f"https://raw.githubusercontent.com/ccfddl/ccf-deadlines/main/conference/data/{cat}.yml"
            response = requests.get(url, timeout=15)
            if response.status_code == 200:
                # 간단한 YAML 파싱 (정규식 사용)
                content = response.text
                confs = parse_simple_yaml(content)
                for conf in confs:
                    conf["source"] = "ccfddl"
                    conf["ccf_category"] = cat
                deadlines.extend(confs)
                print(f"[ccfddl/{cat}] Fetched {len(confs)} conferences")
        except Exception as e:
            print(f"[ccfddl/{cat}] Error: {e}")
    return deadlines


def parse_simple_yaml(content):
    """간단한 YAML 파싱 (PyYAML 없이)"""
    conferences = []
    current_conf = {}
    current_deadline = {}
    in_deadline = False
    
    for line in content.split('\n'):
        line = line.rstrip()
        
        if line.startswith('- title:'):
            if current_conf:
                conferences.append(current_conf)
            current_conf = {"name": line.split(':', 1)[1].strip().strip('"')}
            current_deadline = {}
            in_deadline = False
            
        elif line.strip().startswith('description:'):
            current_conf["full_name"] = line.split(':', 1)[1].strip().strip('"')
            
        elif line.strip().startswith('sub:'):
            current_conf["sub"] = line.split(':', 1)[1].strip()
            
        elif line.strip().startswith('rank:'):
            current_conf["rank"] = line.split(':', 1)[1].strip()
            
        elif line.strip() == '- deadline:' or line.strip().startswith("- deadline: '"):
            in_deadline = True
            if "'" in line:
                # inline deadline
                match = re.search(r"deadline:\s*'([^']+)'", line)
                if match:
                    current_deadline["deadline"] = match.group(1)
                    
        elif in_deadline and line.strip().startswith("deadline:"):
            match = re.search(r"deadline:\s*'([^']+)'", line)
            if match:
                current_deadline["deadline"] = match.group(1)
                
        elif in_deadline and line.strip().startswith("timezone:"):
            current_deadline["timezone"] = line.split(':', 1)[1].strip()
            
        elif line.strip().startswith('link:'):
            current_conf["link"] = line.split(':', 1)[1].strip()
            
        elif line.strip().startswith('place:'):
            current_conf["place"] = line.split(':', 1)[1].strip().strip('"')
            
        elif line.strip().startswith('year:'):
            current_conf["year"] = line.split(':', 1)[1].strip()
    
    if current_conf:
        if current_deadline:
            current_conf.update(current_deadline)
        conferences.append(current_conf)
    
    return conferences


def fetch_from_sec_deadlines():
    """sec-deadlines에서 보안 학회 데드라인 가져오기"""
    deadlines = []
    try:
        url = "https://sec-deadlines.github.io/assets/data/conferences.json"
        response = requests.get(url, timeout=15)
        if response.status_code == 200:
            data = response.json()
            for conf in data:
                deadlines.append({
                    "name": conf.get("name", ""),
                    "full_name": conf.get("full_name", ""),
                    "deadline": conf.get("deadline", ""),
                    "timezone": conf.get("timezone", "UTC"),
                    "link": conf.get("link", ""),
                    "place": conf.get("place", ""),
                    "source": "sec-deadlines"
                })
            print(f"[sec-deadlines] Fetched {len(deadlines)} conferences")
    except Exception as e:
        print(f"[sec-deadlines] Error: {e}")
    return deadlines


def parse_deadline(deadline_str, timezone="UTC"):
    """다양한 데드라인 형식 파싱"""
    if not deadline_str:
        return None
    
    # TBD, TBA 등 처리
    if any(x in deadline_str.upper() for x in ["TBD", "TBA", "N/A"]):
        return None
    
    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
        "%Y-%m-%dT%H:%M:%S",
        "%B %d, %Y",
        "%b %d, %Y",
        "%d %B %Y",
        "%d %b %Y",
    ]
    
    # 날짜 문자열 정리
    clean_str = deadline_str.strip().replace("'", "").replace('"', '')
    
    for fmt in formats:
        try:
            return datetime.strptime(clean_str, fmt)
        except ValueError:
            continue
    
    # ISO format 시도
    try:
        return datetime.fromisoformat(clean_str.replace('Z', '+00:00').split('+')[0])
    except:
        pass
    
    return None


def is_target_conference(conf_name, full_name=""):
    """타겟 학회인지 확인하고 카테고리 반환"""
    name_lower = conf_name.lower()
    full_lower = full_name.lower() if full_name else ""
    
    for category, targets in TARGET_CONFERENCES.items():
        for target in targets:
            if target in name_lower or target in full_lower:
                return category
    return None


def collect_all_deadlines():
    """모든 소스에서 데드라인 수집"""
    all_deadlines = []
    
    # 각 소스에서 수집
    all_deadlines.extend(fetch_from_aideadlines())
    all_deadlines.extend(fetch_from_sec_deadlines())
    all_deadlines.extend(fetch_from_ccfddl())
    
    # 필터링 및 정제
    filtered = []
    seen = set()
    
    for conf in all_deadlines:
        name = conf.get("name", "")
        full_name = conf.get("full_name", "")
        
        # 타겟 학회인지 확인
        category = is_target_conference(name, full_name)
        if not category:
            continue
        
        # 데드라인 파싱
        deadline_str = conf.get("deadline", "")
        deadline_date = parse_deadline(deadline_str, conf.get("timezone", "UTC"))
        
        if not deadline_date:
            continue
        
        # 중복 제거 (학회명 + 연도)
        year = deadline_date.year
        key = f"{name.lower()}_{year}"
        if key in seen:
            continue
        seen.add(key)
        
        filtered.append({
            "name": name,
            "full_name": full_name,
            "category": category,
            "deadline": deadline_date,
            "deadline_str": deadline_str,
            "place": conf.get("place", "TBA"),
            "link": conf.get("link", ""),
            "source": conf.get("source", "unknown"),
        })
    
    print(f"Total filtered conferences: {len(filtered)}")
    return filtered


def get_upcoming_deadlines(deadlines):
    """현재 연도 + 다음 연도까지의 미래 데드라인 필터링"""
    today = datetime.now()
    current_year = today.year
    next_year = current_year + 1
    upcoming = []
    
    for d in deadlines:
        if d['deadline']:
            deadline_year = d['deadline'].year
            days_left = (d['deadline'] - today).days
            
            # 과거가 아니고, 현재 연도 또는 다음 연도인 것만
            if days_left >= 0 and deadline_year <= next_year:
                d['days_left'] = days_left
                upcoming.append(d)
    
    upcoming.sort(key=lambda x: x['deadline'])
    return upcoming


def format_slack_message(deadlines):
    """Slack 메시지 포맷팅"""
    current_year = datetime.now().year
    
    if not deadlines:
        return {
            "text": f"📅 *Conference Deadline Alert*\n\n{current_year}-{current_year+1} 예정된 학회 데드라인이 없습니다."
        }
    
    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "📅 Conference Deadline Alert",
                "emoji": True
            }
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*{current_year}-{current_year+1} 예정된 데드라인: {len(deadlines)}개*"
            }
        },
        {"type": "divider"}
    ]
    
    for d in deadlines:
        days_left = d['days_left']
        
        if days_left <= 3:
            emoji = "🔴"
            urgency = "D-DAY!" if days_left == 0 else f"D-{days_left}"
        elif days_left <= 7:
            emoji = "🟠"
            urgency = f"D-{days_left}"
        elif days_left <= 14:
            emoji = "🟡"
            urgency = f"D-{days_left}"
        else:
            emoji = "🟢"
            urgency = f"D-{days_left}"
        
        conf_name = d['name']
        if d.get('link'):
            conf_name = f"<{d['link']}|{d['name']}>"
        
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"{emoji} *{conf_name}*\n"
                        f"📁 {d['category']} | ⏰ {urgency}\n"
                        f"📆 {d['deadline'].strftime('%Y-%m-%d %H:%M')} | 📍 {d.get('place', 'TBA')}"
            }
        })
    
    blocks.append({"type": "divider"})
    blocks.append({
        "type": "context",
        "elements": [
            {
                "type": "mrkdwn",
                "text": f"Updated: {datetime.now().strftime('%Y-%m-%d %H:%M')} KST | Sources: aideadlines, sec-deadlines, ccfddl"
            }
        ]
    })
    
    return {"blocks": blocks}


def send_slack_notification(message):
    """Slack으로 메시지 전송"""
    if not SLACK_WEBHOOK_URL:
        print("SLACK_WEBHOOK_URL not set")
        return False
    
    try:
        response = requests.post(
            SLACK_WEBHOOK_URL,
            json=message,
            headers={'Content-Type': 'application/json'}
        )
        if response.status_code != 200:
            print(f"Slack error: {response.status_code} - {response.text}")
        return response.status_code == 200
    except Exception as e:
        print(f"Error sending Slack notification: {e}")
        return False


def main():
    print("="*50)
    print("Conference Deadline Alert Bot v2")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*50)
    
    # 데드라인 수집
    deadlines = collect_all_deadlines()
    
    # 현재 연도 + 다음 연도까지의 미래 데드라인
    upcoming = get_upcoming_deadlines(deadlines)
    current_year = datetime.now().year
    print(f"Upcoming deadlines ({current_year}-{current_year+1}): {len(upcoming)}")
    
    # 결과 출력
    for d in upcoming:
        print(f"  [{d['category']}] {d['name']}: {d['deadline'].strftime('%Y-%m-%d')} (D-{d['days_left']})")
    
    # Slack 메시지 생성 및 전송
    message = format_slack_message(upcoming)
    
    if send_slack_notification(message):
        print("\n✅ Slack notification sent successfully!")
    else:
        print("\n❌ Failed to send Slack notification")
        print(json.dumps(message, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()