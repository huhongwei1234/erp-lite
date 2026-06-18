import uuid
import hashlib
import platform

def get_machine_code():
    """
    生成机器码：基于MAC地址和系统信息生成唯一标识
    """
    # 获取MAC地址
    mac = uuid.getnode()
    mac_str = ':'.join(('%012X' % mac)[i:i+2] for i in range(0, 12, 2))
    
    # 获取系统信息
    system_info = f"{platform.system()}-{platform.machine()}-{platform.node()}"
    
    # 组合并哈希
    raw = f"{mac_str}-{system_info}"
    machine_code = hashlib.sha256(raw.encode()).hexdigest()[:32].upper()
    
    return machine_code
