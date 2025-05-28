import os

def delete_files_with_keyword(folder_path, keyword):
    """
    遍历指定文件夹（包括子文件夹），删除文件名中包含特定字符串的文件。

    Args:
        folder_path (str): 要遍历的文件夹路径。
        keyword (str): 要查找的文件名中的关键词。
    """
    deleted_count = 0
    print(f"开始在 '{folder_path}' 中查找并删除包含关键词 '{keyword}' 的文件...")

    for root, dirs, files in os.walk(folder_path):
        for file in files:
            if keyword in file:
                file_path = os.path.join(root, file)
                try:
                    os.remove(file_path)
                    print(f"已删除: {file_path}")
                    deleted_count += 1
                except OSError as e:
                    print(f"删除失败 {file_path}: {e}")
    
    print(f"\n删除完成。总共删除了 {deleted_count} 个文件。")

if __name__ == "__main__":
    # --- 配置你的参数 ---
    # 替换成你要操作的文件夹路径
    target_folder = "./" 
    # 替换成你要查找的关键词
    search_keyword = "NBt23TwZWB3MMjbfNiSd" 
    # -------------------

    # 检查文件夹是否存在
    if not os.path.isdir(target_folder):
        print(f"错误: 文件夹 '{target_folder}' 不存在。请检查路径是否正确。")
    else:
        # 在执行删除操作前，建议先确认一下
        confirmation = input(f"你确定要在 '{target_folder}' 中删除所有文件名包含 '{search_keyword}' 的文件吗？(y/N): ")
        if confirmation.lower() == 'y':
            delete_files_with_keyword(target_folder, search_keyword)
        else:
            print("操作已取消。")