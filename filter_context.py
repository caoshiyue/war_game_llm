import os
import shutil

def copy_files_with_term(source_folder, destination_folder, search_term, search_in_content=False):
    """
    检索指定文件夹下的所有文件，如果文件名或文件内容包含特定字段，则将文件复制到指定路径下。

    Args:
        source_folder (str): 要检索的源文件夹路径。
        destination_folder (str): 找到符合条件的文件后，要复制到的目标文件夹路径。
        search_term (str): 要查找的特定字段。
        search_in_content (bool): 是否搜索文件内容。默认为 False (只搜索文件名)。
    """

    # 确保目标文件夹存在，如果不存在则创建
    if not os.path.exists(destination_folder):
        os.makedirs(destination_folder)
        print(f"已创建目标文件夹: {destination_folder}")

    found_files_count = 0
    print(f"开始在 '{source_folder}' 中搜索包含 '{search_term}' 的文件...")

    for root, _, files in os.walk(source_folder):
        for filename in files:
            source_path = os.path.join(root, filename)
            destination_path = os.path.join(destination_folder, filename)

            # 1. 检查文件名是否包含特定字段
            if search_term.lower() in filename.lower():
                print(f"  [匹配文件名] 发现文件: {source_path}")
                shutil.copy2(source_path, destination_path)
                found_files_count += 1
                continue # 文件名匹配，无需再检查内容

            # 2. 如果开启了内容搜索，则检查文件内容
            if search_in_content:
                try:
                    with open(source_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                        if search_term.lower() in content.lower():
                            print(f"  [匹配内容] 发现文件: {source_path}")
                            shutil.copy2(source_path, destination_path)
                            found_files_count += 1
                except Exception as e:
                    print(f"  [警告] 无法读取文件内容或编码问题: {source_path} - {e}")

    print(f"\n搜索完成。共复制了 {found_files_count} 个文件到 '{destination_folder}'。")

if __name__ == "__main__":
    # --- 配置参数 ---
    # 你要检索的文件夹路径
    source_folder = "data/section1"  # 请替换为你的源文件夹路径
    # 找到符合条件的文件后，要复制到的目标文件夹路径
    destination_folder = "data/section4" # 请替换为你的目标文件夹路径
    # 你要查找的特定字段 (不区分大小写)
    search_term = "无人战车"
    # 是否搜索文件内容 (True 搜索文件名和内容, False 只搜索文件名)
    search_in_content = True
    # --- 配置结束 ---

    copy_files_with_term(source_folder, destination_folder, search_term, search_in_content)