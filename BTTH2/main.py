import re
from typing import Optional
from fastapi import FastAPI, HTTPException, Path, Query, status
from pydantic import BaseModel

app = FastAPI()

# ==========================================
# 1. DỮ LIỆU GIẢ LẬP BAN ĐẦU
# ==========================================
assets = [
    {"id": 1, "serial_number": "SN-MAC-01", "model": "MacBook Pro M3", "stock_available": 5, "status": "READY"},
    {"id": 2, "serial_number": "SN-DELL-02", "model": "Dell UltraSharp 27", "stock_available": 10, "status": "READY"},
    {"id": 3, "serial_number": "SN-THINK-03", "model": "ThinkPad X1 Carbon", "stock_available": 0, "status": "REPAIRING"}
]

allocations = [
    {
        "id": 1,
        "asset_id": 1,
        "employee_email": "dev.nguyen@company.com",
        "allocated_quantity": 1,
        "start_date": "2026-07-01",
        "duration_months": 12
    }
]

# Khuôn mẫu nhận dữ liệu gửi lên
class AssetInput(BaseModel):
    serial_number: str
    model: str
    stock_available: int
    status: str

class AllocationInput(BaseModel):
    asset_id: int
    employee_email: str
    allocated_quantity: int
    start_date: str
    duration_months: int


# ==========================================
# 2. CÁC API QUẢN LÝ TÀI SẢN (ASSETS)
# ==========================================

# Khai báo tài sản mới
@app.post("/assets", status_code=201)
def create_asset(data: AssetInput):
    if not (2 <= len(data.model) <= 255):
        raise HTTPException(status_code=400, detail="Độ dài tên model phải từ 2 đến 255 ký tự.")
    if data.stock_available < 0:
        raise HTTPException(status_code=400, detail="Số lượng tồn kho phải lớn hơn hoặc bằng 0.")
    if data.status not in ["READY", "ALLOCATED", "REPAIRING", "SCRAPPED"]:
        raise HTTPException(status_code=400, detail="Trạng thái tài sản không hợp lệ.")
    
    # Kiểm tra trùng serial_number
    for a in assets:
        if a["serial_number"].upper() == data.serial_number.upper():
            raise HTTPException(status_code=400, detail="Mã Serial Number này đã tồn tại.")

    new_asset = {
        "id": max([a["id"] for a in assets], default=0) + 1,
        "serial_number": data.serial_number.upper(),
        "model": data.model,
        "stock_available": data.stock_available,
        "status": data.status
    }
    assets.append(new_asset)
    return new_asset

# Xem danh mục thiết bị + Tìm kiếm Regex & Bộ lọc
@app.get("/assets")
def get_assets(keyword: Optional[str] = None, status: Optional[str] = None, min_stock: Optional[int] = None):
    results = assets.copy()
    
    if keyword:
        results = [a for a in results if keyword.lower() in a["model"].lower() or keyword.lower() in a["serial_number"].lower()]
    if status:
        results = [a for a in results if a["status"] == status]
    if min_stock is not None:
        results = [a for a in results if a["stock_available"] >= min_stock]
        
    return results

# Lấy thông tin chi tiết một tài sản
@app.get("/assets/{asset_id}")
def get_asset_detail(asset_id: int):
    for a in assets:
        if a["id"] == asset_id:
            return a
    raise HTTPException(status_code=404, detail="Asset not found")

# Cập nhật cấu hình tài sản
@app.put("/assets/{asset_id}")
def update_asset(asset_id: int, data: AssetInput):
    for a in assets:
        if a["id"] == asset_id:
            a["serial_number"] = data.serial_number.upper()
            a["model"] = data.model
            a["stock_available"] = data.stock_available
            a["status"] = data.status
            return a
    raise HTTPException(status_code=404, detail="Asset not found")

# Xóa tài sản khỏi hệ thống
@app.delete("/assets/{asset_id}")
def delete_asset(asset_id: int):
    for a in assets:
        if a["id"] == asset_id:
            assets.remove(a)
            return {"message": "Đã xóa tài sản thành công."}
    raise HTTPException(status_code=404, detail="Asset not found")


# ==========================================
# 3. API CẤP PHÁT THIẾT BỊ (ALLOCATIONS)
# ==========================================

# Đăng ký cấp phát thiết bị
@app.post("/allocations", status_code=201)
def create_allocation(data: AllocationInput):
    if data.allocated_quantity <= 0:
        raise HTTPException(status_code=400, detail="Số lượng cấp phát phải lớn hơn 0.")
    if not (1 <= data.duration_months <= 12):
        raise HTTPException(status_code=400, detail="Thời gian cho mượn phải từ 1 đến 12 tháng.")

    # KIỂM TRA REGEX EMAIL HỢP LỆ
    email_regex = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
    if not re.match(email_regex, data.employee_email):
        raise HTTPException(status_code=400, detail="Định dạng Email nhân viên không hợp lệ.")

    # Tìm tài sản trong kho
    asset = None
    for a in assets:
        if a["id"] == data.asset_id:
            asset = a
            break

    if not asset:
        raise HTTPException(status_code=404, detail="Thiết bị không tồn tại trong danh mục công ty.")
    if asset["status"] != "READY":
        raise HTTPException(status_code=400, detail="Thiết bị không ở trạng thái sẵn sàng (READY) để bàn giao.")
    if data.allocated_quantity > asset["stock_available"]:
        raise HTTPException(status_code=400, detail="Số lượng yêu cầu vượt quá số lượng tồn kho khả dụng thực tế.")

    # Trừ bớt số lượng tồn kho sau khi cấp phát thành công
    asset["stock_available"] -= data.allocated_quantity

    new_allocation = {
        "id": max([al["id"] for al in allocations], default=0) + 1,
        "asset_id": data.asset_id,
        "employee_email": data.employee_email,
        "allocated_quantity": data.allocated_quantity,
        "start_date": data.start_date,
        "duration_months": data.duration_months
    }
    allocations.append(new_allocation)
    return new_allocation

# Lấy danh sách lịch sử cấp phát
@app.get("/allocations")
def get_allocations():
    return allocations


# Đoạn đuôi để chạy ứng dụng trực tiếp bằng Uvicorn
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)