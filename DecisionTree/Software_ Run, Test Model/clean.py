input_file = "tree.mem"    # file gốc
output_file = "tree_clean.mem"  # file kết quả

with open(input_file, "r") as f_in, open(output_file, "w") as f_out:
    for line in f_in:
        # Lấy phần trước dấu //
        clean_line = line.split("//")[0].strip()
        if clean_line:  # chỉ ghi dòng không rỗng
            f_out.write(clean_line + "\n")

print(f"✅ Đã xóa comment, lưu vào {output_file}")
