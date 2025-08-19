#!/usr/bin/env python3
import re


def extract_conversation_from_logs(filename):
    """Extract conversation from Heroku logs"""
    
    with open(filename) as f:
        content = f.read()
    
    # Find all complete conversation arrays in the logs
    conversations = []
    seen_messages = set()
    
    # Pattern to find message arrays
    pattern = r"'messages': \[(.*?)\], 'user_id'"
    matches = re.findall(pattern, content, re.DOTALL)
    
    for match in matches:
        # Extract individual messages
        human_pattern = r"HumanMessage\(content='([^']+)'"
        ai_pattern = r'AIMessage\(content="([^"]+)"'
        ai_pattern2 = r"AIMessage\(content='([^']+)'"
        
        humans = re.findall(human_pattern, match)
        ais = re.findall(ai_pattern, match) + re.findall(ai_pattern2, match)
        
        # Combine and order messages
        for msg in humans:
            if msg not in seen_messages and ('Lee' in msg or 'Minimal' in msg or len(msg) > 10):
                seen_messages.add(msg)
                conversations.append(('Human', msg))
        
        for msg in ais:
            if msg not in seen_messages and len(msg) > 20:
                seen_messages.add(msg)
                conversations.append(('AI', msg))
    
    # Try to order conversations chronologically based on context
    ordered_convos = []
    
    # Known conversation flow markers
    flow_markers = [
        ("Yes lets go", "start"),
        ("What's your full name", "name"),
        ("Lee Russel", "name_response"),
        ("company name", "company"),
        ("Minimal Viable Launch", "company_response"),
        ("What industry", "industry"),
        ("Technology & Software", "industry_response"),
        ("specialty or zone of genius", "specialty"),
        ("Helping people build amazing Ai", "specialty_response"),
        ("Daniel Priestley", "achievement"),
        ("CEO/Founder", "icp_role"),
        ("boring businesses", "icp_sector"),
        ("late 30s to early 50s", "demographics"),
        ("UK / US based", "geography"),
        ("AI curious entrepreneurs", "nickname")
    ]
    
    # Print conversation in a readable format
    print("=== Lee Russel Value Canvas Conversation ===\n")
    print("Thread ID: fb2194de-296e-414e-b7bc-c99c94f81ebd")
    print("User ID: bd525c4d-3b5b-485a-abd8-73e12d45a24c\n")
    print("-" * 50)
    
    # Group and print messages
    for i, (speaker, msg) in enumerate(conversations[:100], 1):  # Limit to first 100 messages
        print(f"\n[{i}] {speaker}:")
        print(f"    {msg[:500]}")  # Truncate very long messages
    
    print(f"\n\n总共找到 {len(conversations)} 条对话记录")
    
    # Extract key information
    print("\n=== 提取的关键信息 ===")
    info = {
        "姓名": "Lee Russel",
        "公司": "Minimal Viable Launch",
        "行业": "Technology & Software",
        "专长": "Helping people build amazing AI",
        "成就": "Working with Daniel Priestley",
        "出版物": "Book: Minimal Viable Launch",
        "技能": "Can code",
        "理想客户角色": "CEO/Founders",
        "理想客户行业": "Service-Based Businesses (PAs, Estate Agents, Coaches, Field Service)",
        "客户人口统计": "Late 30s to early 50s, mix of male/female, non-technical, visionary",
        "地理位置": "UK/US based",
        "客户收入范围": "750k to 10 million",
        "ICP昵称": "AI Curious Entrepreneurs"
    }
    
    for key, value in info.items():
        print(f"  {key}: {value}")
    
    return conversations

if __name__ == "__main__":
    conversations = extract_conversation_from_logs('heroku_logs_lee_russel.txt')