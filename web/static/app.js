document.addEventListener('DOMContentLoaded', () => {
    loadAllData();

    // Form Tạo Danh Mục
    document.getElementById('form-category').addEventListener('submit', async (e) => {
        e.preventDefault();
        const name = document.getElementById('cat-name').value;
        const price = document.getElementById('cat-price').value;
        const description = document.getElementById('cat-desc').value;

        try {
            const res = await fetch('/api/categories/add', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name, price: parseFloat(price), description })
            });
            const data = await res.json();
            if (res.ok && data.success) {
                alert('✅ Đã tạo danh mục thành công!');
                document.getElementById('form-category').reset();
                loadAllData();
            } else {
                alert('❌ Lỗi: ' + (data.message || 'Không thể tạo danh mục'));
            }
        } catch (err) {
            alert('❌ Lỗi kết nối server!');
        }
    });

    // Form Nạp Stock
    document.getElementById('form-stock').addEventListener('submit', async (e) => {
        e.preventDefault();
        const category_id = document.getElementById('stock-cat-select').value;
        const items = document.getElementById('stock-items').value;

        try {
            const res = await fetch('/api/stock/add', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ category_id, items })
            });
            const data = await res.json();
            if (res.ok && data.success) {
                alert(`✅ Đã nạp thành công ${data.added_count} sản phẩm vào kho!`);
                document.getElementById('form-stock').reset();
                loadAllData();
            } else {
                alert('❌ Lỗi: ' + (data.message || 'Không thể nạp hàng'));
            }
        } catch (err) {
            alert('❌ Lỗi kết nối server!');
        }
    });

    // Form Cộng/Trừ Số Dư
    document.getElementById('form-balance').addEventListener('submit', async (e) => {
        e.preventDefault();
        const user_id = document.getElementById('bal-user-id').value;
        const amount = document.getElementById('bal-amount').value;

        try {
            const res = await fetch('/api/users/balance', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ user_id, amount: parseFloat(amount) })
            });
            const data = await res.json();
            if (res.ok && data.success) {
                alert(`✅ Đã cập nhật số dư mới: ${Math.round(data.new_balance).toLocaleString('vi-VN')} VNĐ`);
                document.getElementById('form-balance').reset();
                loadAllData();
            } else {
                alert('❌ Lỗi: ' + (data.message || 'Không thể cập nhật số dư'));
            }
        } catch (err) {
            alert('❌ Lỗi kết nối server!');
        }
    });

    // Form Lưu Cấu Hình Chữ Cửa Hàng
    const formStoreSettings = document.getElementById('form-store-settings');
    if (formStoreSettings) {
        formStoreSettings.addEventListener('submit', async (e) => {
            e.preventDefault();
            const title = document.getElementById('setting-title').value;
            const description = document.getElementById('setting-desc').value;
            const footer = document.getElementById('setting-footer').value;
            const banner_url = document.getElementById('setting-banner').value;

            try {
                const res = await fetch('/api/settings/store', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ title, description, footer, banner_url })
                });
                const data = await res.json();
                if (res.ok && data.success) {
                    alert('✅ Đã lưu cấu hình chữ Cửa Hàng thành công! Hãy dùng lệnh /setupstore hoặc !setup trên Discord để phát hành bảng mới.');
                    fetchStoreSettings();
                } else {
                    alert('❌ Lỗi: ' + (data.message || 'Không thể lưu cấu hình'));
                }
            } catch (err) {
                alert('❌ Lỗi kết nối server!');
            }
        });
    }
});

async function loadAllData() {
    fetchStats();
    fetchCategories();
    fetchUsers();
    fetchOrders();
    fetchPendingDeposits();
    fetchStoreSettings();
}

async function fetchStoreSettings() {
    try {
        const res = await fetch('/api/settings/store');
        const st = await res.json();
        if (st) {
            if (document.getElementById('setting-title')) document.getElementById('setting-title').value = st.title || '';
            if (document.getElementById('setting-desc')) document.getElementById('setting-desc').value = st.description || '';
            if (document.getElementById('setting-footer')) document.getElementById('setting-footer').value = st.footer || '';
            if (document.getElementById('setting-banner')) document.getElementById('setting-banner').value = st.banner_url || '';
        }
    } catch (err) {
        console.error("Lỗi lấy store settings:", err);
    }
}

async function fetchPendingDeposits() {
    try {
        const res = await fetch('/api/payment/pending');
        const deposits = await res.json();

        const tbody = document.getElementById('pending-deposit-table-body');
        if (!tbody) return;
        tbody.innerHTML = '';

        if (deposits.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="6" class="p-4 text-center text-slate-500 text-xs">
                        ✅ Không có đơn nạp tiền nào đang chờ duyệt. Tất cả đã hoàn tất!
                    </td>
                </tr>
            `;
            return;
        }

        deposits.forEach(d => {
            const tr = document.createElement('tr');
            tr.className = 'hover:bg-slate-800/40 transition-colors text-xs';
            tr.innerHTML = `
                <td class="p-3.5 font-mono text-slate-400">#${d.id}</td>
                <td class="p-3.5 font-semibold text-purple-300">${d.username ? '@' + d.username : d.user_id}</td>
                <td class="p-3.5 font-bold text-emerald-400">${Math.round(d.amount_vnd).toLocaleString('vi-VN')} VNĐ</td>
                <td class="p-3.5 font-mono text-amber-300 bg-slate-900/50 rounded px-2 py-1 select-all">${d.memo}</td>
                <td class="p-3.5 text-slate-500">${d.created_at}</td>
                <td class="p-3.5 text-center">
                    <button onclick="approveDeposit(${d.id}, '${(d.username || d.user_id)}', ${d.amount_vnd})" 
                        class="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white font-bold rounded-lg transition-all shadow-md">
                        ✅ Duyệt Nạp Tiền
                    </button>
                </td>
            `;
            tbody.appendChild(tr);
        });
    } catch (err) {
        console.error("Lỗi lấy pending deposits:", err);
    }
}

async function approveDeposit(depositId, userDisplay, amountVnd) {
    if (!confirm(`⚡ Duyệt cộng ${Math.round(amountVnd).toLocaleString('vi-VN')} VNĐ cho khách hàng "${userDisplay}"?`)) return;

    try {
        const res = await fetch('/api/payment/approve-deposit', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ deposit_id: depositId })
        });
        const data = await res.json();
        if (res.ok && data.success) {
            alert(`🎉 ĐÃ DUYỆT THÀNH CÔNG! Đã cộng ${Math.round(amountVnd).toLocaleString('vi-VN')} VNĐ vào tài khoản.`);
            loadAllData();
        } else {
            alert('❌ Lỗi: ' + (data.message || 'Không thể duyệt đơn nạp này'));
        }
    } catch (err) {
        alert('❌ Lỗi kết nối server!');
    }
}

async function fetchStats() {
    try {
        const res = await fetch('/api/stats');
        const stats = await res.json();
        document.getElementById('stat-revenue').textContent = `${Math.round(stats.total_revenue).toLocaleString('vi-VN')} VNĐ`;
        document.getElementById('stat-orders').textContent = stats.total_orders;
        document.getElementById('stat-stock').textContent = stats.available_stock;
        document.getElementById('stat-users').textContent = stats.total_users;
    } catch (err) {
        console.error("Lỗi lấy stats:", err);
    }
}

async function fetchCategories() {
    try {
        const res = await fetch('/api/categories');
        const categories = await res.json();

        const select = document.getElementById('stock-cat-select');
        select.innerHTML = '<option value="">-- Chọn danh mục --</option>';

        const catList = document.getElementById('category-list');
        catList.innerHTML = '';

        categories.forEach(cat => {
            // Dropdown option
            const opt = document.createElement('option');
            opt.value = cat.id;
            opt.textContent = `${cat.name} (${Math.round(cat.price).toLocaleString('vi-VN')} VNĐ) - Tồn: ${cat.stock_count}`;
            select.appendChild(opt);

            // List item display với nút XÓA
            const div = document.createElement('div');
            div.className = 'p-3 bg-slate-800/80 rounded-lg border border-slate-700/60 flex justify-between items-center text-xs';
            div.innerHTML = `
                <div>
                    <span class="font-bold text-white">[ID ${cat.id}] ${cat.name}</span>
                    <span class="text-emerald-400 font-semibold ml-2">(${Math.round(cat.price).toLocaleString('vi-VN')} VNĐ)</span>
                </div>
                <div class="flex items-center gap-2">
                    <span class="px-2 py-0.5 rounded ${cat.stock_count > 0 ? 'bg-emerald-500/20 text-emerald-400' : 'bg-red-500/20 text-red-400'} font-semibold">
                        Còn ${cat.stock_count} món
                    </span>
                    <button onclick="deleteCategory(${cat.id}, '${cat.name.replace(/'/g, "\\'")}')" class="px-2 py-0.5 bg-red-500/20 hover:bg-red-500/40 text-red-400 font-bold rounded transition-all">
                        🗑️ Xóa
                    </button>
                </div>
            `;
            catList.appendChild(div);
        });
    } catch (err) {
        console.error("Lỗi lấy categories:", err);
    }
}

async function deleteCategory(catId, catName) {
    if (!confirm(`⚠️ Ngài có chắc chắn muốn xóa danh mục "${catName}" (ID: ${catId}) không?`)) return;

    try {
        const res = await fetch('/api/categories/delete', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ category_id: catId })
        });
        const data = await res.json();
        if (res.ok && data.success) {
            alert(`✅ Đã xóa danh mục "${catName}" thành công!`);
            loadAllData();
        } else {
            alert('❌ Lỗi: ' + (data.message || 'Không thể xóa danh mục'));
        }
    } catch (err) {
        alert('❌ Lỗi kết nối server!');
    }
}

async function fetchUsers() {
    try {
        const res = await fetch('/api/users');
        const users = await res.json();

        const tbody = document.getElementById('user-table-body');
        tbody.innerHTML = '';

        users.forEach(u => {
            const tr = document.createElement('tr');
            tr.className = 'hover:bg-slate-800/40 transition-colors';
            tr.innerHTML = `
                <td class="p-3 font-mono font-medium text-purple-300">${u.username ? '@' + u.username + ' (' + u.user_id + ')' : u.user_id}</td>
                <td class="p-3 font-semibold text-emerald-400">${Math.round(u.balance).toLocaleString('vi-VN')} VNĐ</td>
                <td class="p-3 text-slate-500">${u.created_at || 'N/A'}</td>
            `;
            tbody.appendChild(tr);
        });
    } catch (err) {
        console.error("Lỗi lấy users:", err);
    }
}

async function fetchOrders() {
    try {
        const res = await fetch('/api/orders');
        const orders = await res.json();

        const tbody = document.getElementById('order-table-body');
        tbody.innerHTML = '';

        orders.forEach(o => {
            const tr = document.createElement('tr');
            tr.className = 'hover:bg-slate-800/40 transition-colors text-xs';
            tr.innerHTML = `
                <td class="p-3.5 font-mono text-slate-400">#${o.id}</td>
                <td class="p-3.5 font-mono text-purple-300">${o.user_id}</td>
                <td class="p-3.5 font-semibold text-white">${o.category_name}</td>
                <td class="p-3.5 font-semibold text-emerald-400">${Math.round(o.price).toLocaleString('vi-VN')} VNĐ</td>
                <td class="p-3.5 font-mono text-amber-300 bg-slate-900/50 rounded px-2 py-1 select-all">${o.item_data}</td>
                <td class="p-3.5 text-slate-500">${o.created_at}</td>
            `;
            tbody.appendChild(tr);
        });
    } catch (err) {
        console.error("Lỗi lấy orders:", err);
    }
}
