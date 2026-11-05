/* Projeck — hệ thống quản lý dự án & giao việc cho công ty lập trình.
 * Chạy hoàn toàn trên trình duyệt, không cần cài đặt. Dữ liệu lưu trong localStorage
 * và có thể xuất/nhập file JSON để sao lưu hoặc chia sẻ. */
(() => {
  'use strict';

  const KEY = 'projeck.v1';
  const STATUSES = [
    { id: 'todo', label: 'Chờ làm' },
    { id: 'doing', label: 'Đang làm' },
    { id: 'review', label: 'Chờ duyệt' },
    { id: 'done', label: 'Hoàn thành' },
  ];
  const PRIORITIES = { urgent: 'Khẩn', high: 'Cao', normal: 'Thường', low: 'Thấp' };
  const PROJECT_STATUS = { active: 'Đang chạy', paused: 'Tạm dừng', closed: 'Đã đóng' };

  // ---------- Tiện ích ----------
  const $ = (sel) => document.querySelector(sel);
  const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const uid = (p) => `${p}-${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`;
  const pad = (n) => String(n).padStart(2, '0');
  const isoDate = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
  const todayIso = () => isoDate(new Date());
  const addDays = (n) => { const d = new Date(); d.setDate(d.getDate() + n); return isoDate(d); };
  const fmtDate = (s) => (s ? s.split('-').reverse().join('/') : '—');
  const isOverdue = (t) => Boolean(t.due) && t.status !== 'done' && t.due < todayIso();

  // ---------- Dữ liệu mẫu: đủ các bộ phận của một công ty phần mềm ----------
  function seed() {
    const departments = [
      ['d-bgd', 'Ban Giám đốc', 'Định hướng chiến lược, phê duyệt ngân sách, dự án và nhân sự chủ chốt'],
      ['d-pmo', 'Quản lý dự án (PMO)', 'Lập kế hoạch, chia việc, theo dõi tiến độ, quản trị rủi ro'],
      ['d-ba', 'Phân tích nghiệp vụ (BA)', 'Thu thập yêu cầu, viết đặc tả, làm cầu nối khách hàng – kỹ thuật'],
      ['d-be', 'Phát triển Backend', 'API, cơ sở dữ liệu, dịch vụ nền, tích hợp hệ thống'],
      ['d-fe', 'Phát triển Frontend', 'Giao diện web, hiệu năng và trải nghiệm phía người dùng'],
      ['d-mob', 'Phát triển Mobile', 'Ứng dụng iOS và Android'],
      ['d-uiux', 'Thiết kế UI/UX', 'Nghiên cứu người dùng, wireframe, prototype, hệ thống thiết kế'],
      ['d-qa', 'Kiểm thử (QA/QC)', 'Kế hoạch test, test thủ công và tự động, kiểm soát chất lượng'],
      ['d-devops', 'DevOps & Hạ tầng', 'CI/CD, máy chủ, cloud, giám sát, sao lưu'],
      ['d-sec', 'Bảo mật thông tin', 'Đánh giá bảo mật, kiểm soát truy cập, tuân thủ'],
      ['d-sup', 'Hỗ trợ khách hàng', 'Tiếp nhận và xử lý yêu cầu, sự cố từ khách hàng'],
      ['d-sales', 'Kinh doanh & Marketing', 'Tìm khách hàng, báo giá, hợp đồng, truyền thông'],
      ['d-hr', 'Nhân sự (HR)', 'Tuyển dụng, đào tạo, đánh giá hiệu suất, chế độ'],
      ['d-fin', 'Kế toán – Tài chính', 'Thanh toán, công nợ, lương, báo cáo tài chính'],
      ['d-admin', 'Hành chính – Văn phòng', 'Cơ sở vật chất, thiết bị, văn thư, mua sắm'],
    ].map(([id, name, desc]) => ({ id, name, desc, head: '' }));

    // Tên nhân sự là dữ liệu MẪU — thay bằng nhân sự thật của công ty.
    const members = [
      ['m-ceo', 'Lê Thành Đạt', 'd-bgd', 'Giám đốc điều hành (CEO)', 'Chiến lược, quản trị', 3],
      ['m-cto', 'Võ Hoàng Nam', 'd-bgd', 'Giám đốc kỹ thuật (CTO)', 'Kiến trúc hệ thống', 4],
      ['m-pm', 'Nguyễn Minh Anh', 'd-pmo', 'Trưởng PMO', 'Agile, Scrum', 6],
      ['m-ba', 'Châu Ngọc Diệp', 'd-ba', 'Business Analyst', 'Đặc tả, BPMN', 6],
      ['m-be', 'Trần Quốc Bảo', 'd-be', 'Trưởng nhóm Backend', 'Node.js, PostgreSQL', 6],
      ['m-be2', 'Lâm Tuấn Kiệt', 'd-be', 'Backend Developer', 'Java, Spring', 6],
      ['m-fe', 'Phạm Thu Hà', 'd-fe', 'Trưởng nhóm Frontend', 'React, TypeScript', 6],
      ['m-mob', 'Vũ Đức Long', 'd-mob', 'Mobile Developer', 'Flutter, Kotlin', 6],
      ['m-ux', 'Hoàng Lan Chi', 'd-uiux', 'UI/UX Designer', 'Figma, Research', 6],
      ['m-qa', 'Đỗ Hải Yến', 'd-qa', 'QA Lead', 'Test plan, Playwright', 6],
      ['m-ops', 'Bùi Văn Khoa', 'd-devops', 'DevOps Engineer', 'Docker, Kubernetes', 6],
      ['m-sec', 'Ngô Gia Huy', 'd-sec', 'Security Engineer', 'OWASP, Pentest', 5],
      ['m-sup', 'Lý Thanh Tâm', 'd-sup', 'Trưởng bộ phận CSKH', 'Ticketing, CRM', 8],
      ['m-sales', 'Đặng Minh Quân', 'd-sales', 'Account Manager', 'Đàm phán, CRM', 6],
      ['m-hr', 'Trịnh Thu Trang', 'd-hr', 'Chuyên viên nhân sự', 'Tuyển dụng, Đào tạo', 6],
      ['m-fin', 'Phan Ngọc Ánh', 'd-fin', 'Kế toán trưởng', 'Kế toán, Thuế', 6],
      ['m-admin', 'Mai Đình Sơn', 'd-admin', 'Nhân viên hành chính', 'Mua sắm, Văn thư', 6],
    ].map(([id, name, deptId, title, skills, capacity]) => ({ id, name, deptId, title, skills, capacity }));

    const heads = {
      'd-bgd': 'm-ceo', 'd-pmo': 'm-pm', 'd-ba': 'm-ba', 'd-be': 'm-be', 'd-fe': 'm-fe', 'd-mob': 'm-mob',
      'd-uiux': 'm-ux', 'd-qa': 'm-qa', 'd-devops': 'm-ops', 'd-sec': 'm-sec', 'd-sup': 'm-sup',
      'd-sales': 'm-sales', 'd-hr': 'm-hr', 'd-fin': 'm-fin', 'd-admin': 'm-admin',
    };
    departments.forEach((d) => { d.head = heads[d.id] || ''; });

    const projects = [
      { id: 'p-1', code: 'PRJ-001', name: 'Website thương mại điện tử cho khách hàng A', deptId: 'd-pmo',
        ownerId: 'm-pm', start: addDays(-14), due: addDays(45), status: 'active',
        desc: 'Web bán hàng + trang quản trị, thanh toán online' },
      { id: 'p-2', code: 'PRJ-002', name: 'Ứng dụng mobile đặt lịch', deptId: 'd-mob',
        ownerId: 'm-pm', start: addDays(-3), due: addDays(75), status: 'active',
        desc: 'App iOS/Android đặt lịch hẹn, thông báo đẩy' },
      { id: 'p-3', code: 'PRJ-003', name: 'Vận hành nội bộ công ty', deptId: 'd-bgd',
        ownerId: 'm-ceo', start: addDays(-30), due: '', status: 'active',
        desc: 'Tuyển dụng, tài chính, hành chính, hạ tầng nội bộ' },
    ];

    const tasks = [
      ['p-1', 'Lập kế hoạch sprint 1 và phân công', 'm-pm', 'normal', 'done', -12, 3],
      ['p-1', 'Viết đặc tả yêu cầu giỏ hàng & thanh toán', 'm-ba', 'high', 'done', -8, 8],
      ['p-1', 'Thiết kế wireframe trang sản phẩm', 'm-ux', 'high', 'review', 2, 8],
      ['p-1', 'Xây dựng API đơn hàng', 'm-be', 'urgent', 'doing', 5, 16],
      ['p-1', 'Dựng giao diện trang danh sách sản phẩm', 'm-fe', 'normal', 'doing', 7, 12],
      ['p-1', 'Thiết lập pipeline CI/CD và môi trường staging', 'm-ops', 'high', 'todo', 4, 10],
      ['p-1', 'Rà soát bảo mật luồng đăng nhập', 'm-sec', 'high', 'todo', -1, 6],
      ['p-1', 'Viết kịch bản kiểm thử hồi quy', 'm-qa', 'normal', 'todo', 10, 6],
      ['p-2', 'Khung ứng dụng Flutter và điều hướng', 'm-mob', 'high', 'doing', 6, 12],
      ['p-2', 'API đặt lịch và thông báo đẩy', 'm-be2', 'normal', 'todo', 12, 14],
      ['p-2', 'Tài liệu hướng dẫn sử dụng cho khách', 'm-sup', 'low', 'todo', 40, 4],
      ['p-3', 'Tuyển 2 lập trình viên Backend', 'm-hr', 'high', 'doing', 20, 20],
      ['p-3', 'Báo giá và hợp đồng cho khách hàng mới', 'm-sales', 'urgent', 'todo', 3, 5],
      ['p-3', 'Chốt bảng lương và công nợ tháng', 'm-fin', 'normal', 'todo', 8, 6],
      ['p-3', 'Mua thiết bị cho nhân sự mới', 'm-admin', 'low', 'todo', 15, 3],
    ].map(([projectId, title, assigneeId, priority, status, due, estimate], i) => ({
      id: `t-${i + 1}`, projectId, title, desc: '', assigneeId, priority, status,
      due: addDays(due), estimate, createdAt: addDays(-14),
    }));

    return { version: 1, departments, members, projects, tasks };
  }

  // ---------- Lưu trữ ----------
  function isValidData(d) {
    return d && ['departments', 'members', 'projects', 'tasks'].every((k) => Array.isArray(d[k]));
  }
  function load() {
    try {
      const raw = localStorage.getItem(KEY);
      if (raw) {
        const d = JSON.parse(raw);
        if (isValidData(d)) return d;
      }
    } catch (e) { /* trình duyệt chặn lưu trữ hoặc dữ liệu hỏng: dùng dữ liệu mẫu */ }
    return seed();
  }
  function save() {
    try { localStorage.setItem(KEY, JSON.stringify(state)); return true; } catch (e) {
      toast('Trình duyệt không cho lưu — hãy Xuất JSON để giữ dữ liệu');
      return false;
    }
  }
  function commit(msg) { save(); render(); if (msg) toast(msg); }

  let state = load();
  const filters = { project: '', assignee: '', dept: '', q: '' };

  // ---------- Tra cứu ----------
  const findById = (list, id) => list.find((x) => x.id === id);
  const dept = (id) => findById(state.departments, id);
  const member = (id) => findById(state.members, id);
  const project = (id) => findById(state.projects, id);
  const task = (id) => findById(state.tasks, id);
  const memberName = (id) => member(id)?.name ?? 'Chưa giao';
  const openTasks = (mid) => state.tasks.filter((t) => t.assigneeId === mid && t.status !== 'done');

  function selectOpts(list, selected, emptyLabel) {
    const empty = emptyLabel != null ? `<option value="">${esc(emptyLabel)}</option>` : '';
    return empty + list.map((o) =>
      `<option value="${esc(o.id)}"${o.id === selected ? ' selected' : ''}>${esc(o.label)}</option>`).join('');
  }
  const memberOpts = (sel, empty) => selectOpts(state.members.map((m) => {
    const d = dept(m.deptId);
    return { id: m.id, label: d ? `${m.name} — ${d.name}` : m.name };
  }), sel, empty);
  const projectOpts = (sel, empty) =>
    selectOpts(state.projects.map((p) => ({ id: p.id, label: `${p.code} · ${p.name}` })), sel, empty);
  const deptOpts = (sel, empty) =>
    selectOpts(state.departments.map((d) => ({ id: d.id, label: d.name })), sel, empty);
  const mapOpts = (obj, sel) => Object.entries(obj)
    .map(([k, v]) => `<option value="${k}"${k === sel ? ' selected' : ''}>${v}</option>`).join('');
  const badgePri = (p) => `<span class="badge pri-${esc(p)}">${esc(PRIORITIES[p] || p)}</span>`;

  // ---------- Màn hình: Tổng quan ----------
  function viewOverview() {
    const all = state.tasks;
    const count = (s) => all.filter((t) => t.status === s).length;
    const overdue = all.filter(isOverdue).sort((a, b) => a.due.localeCompare(b.due));
    const unassigned = all.filter((t) => !t.assigneeId && t.status !== 'done');
    const pct = all.length ? Math.round((count('done') / all.length) * 100) : 0;
    const stats = [
      ['Tổng công việc', all.length], ['Đang làm', count('doing')], ['Chờ duyệt', count('review')],
      ['Quá hạn', overdue.length, overdue.length ? 'late' : ''], ['Chưa giao', unassigned.length],
      ['Hoàn thành', `${pct}%`],
    ].map(([label, val, cls = '']) =>
      `<div class="stat ${cls}"><div class="val">${val}</div><div class="muted">${label}</div></div>`).join('');

    const rows = state.members.map((m) => {
      const open = openTasks(m.id);
      const late = open.filter(isOverdue).length;
      const ratio = m.capacity ? Math.round((open.length / m.capacity) * 100) : (open.length ? 100 : 0);
      return `<tr>
        <td><strong>${esc(m.name)}</strong><div class="muted small">${esc(m.title)}</div></td>
        <td>${esc(dept(m.deptId)?.name ?? '—')}</td>
        <td class="num">${open.length} / ${esc(m.capacity)}</td>
        <td><div class="bar" title="${ratio}% sức chứa"><span class="${ratio >= 100 ? 'over' : ''}" style="width:${Math.min(ratio, 100)}%"></span></div></td>
        <td class="num ${late ? 'late' : ''}">${late}</td>
      </tr>`;
    }).join('');

    const lateList = overdue.length
      ? `<ul class="list">${overdue.map((t) => `<li><strong>${esc(t.title)}</strong> — ${esc(memberName(t.assigneeId))}, hạn ${fmtDate(t.due)}</li>`).join('')}</ul>`
      : '<p class="muted">Không có việc quá hạn.</p>';

    return `
      <div class="stats">${stats}</div>
      <h2>Việc quá hạn</h2>
      <div class="panel">${lateList}</div>
      <h2>Khối lượng công việc theo nhân sự</h2>
      <div class="table-wrap"><table>
        <thead><tr><th>Nhân sự</th><th>Bộ phận</th><th class="num">Việc mở / Sức chứa</th><th>Tải</th><th class="num">Quá hạn</th></tr></thead>
        <tbody>${rows || '<tr><td colspan="5" class="muted">Chưa có nhân sự.</td></tr>'}</tbody>
      </table></div>`;
  }

  // ---------- Màn hình: Công việc (Kanban + giao việc) ----------
  function taskCard(t) {
    const p = project(t.projectId);
    const late = isOverdue(t);
    return `<article class="card${late ? ' overdue' : ''}" draggable="true" data-task="${esc(t.id)}">
      <div class="card-top">${badgePri(t.priority)}<span class="muted">${esc(p?.code ?? '')}</span></div>
      <h4>${esc(t.title)}</h4>
      ${t.desc ? `<div class="small muted">${esc(t.desc)}</div>` : ''}
      <div class="small ${late ? 'late' : 'muted'}">${t.due ? `Hạn ${fmtDate(t.due)}${late ? ' · quá hạn' : ''}` : 'Không đặt hạn'} · ${esc(t.estimate || 0)}h</div>
      <div class="row">
        <select data-change="assignee" data-id="${esc(t.id)}" aria-label="Người thực hiện">${memberOpts(t.assigneeId, 'Chưa giao')}</select>
        <select data-change="status" data-id="${esc(t.id)}" aria-label="Trạng thái">${STATUSES.map((s) =>
          `<option value="${s.id}"${s.id === t.status ? ' selected' : ''}>${s.label}</option>`).join('')}</select>
      </div>
      <button type="button" class="link danger small" data-action="del-task" data-id="${esc(t.id)}">Xóa</button>
    </article>`;
  }

  function viewBoard() {
    const q = filters.q.trim().toLowerCase();
    const list = state.tasks.filter((t) =>
      (!filters.project || t.projectId === filters.project) &&
      (!filters.assignee || t.assigneeId === filters.assignee) &&
      (!filters.dept || member(t.assigneeId)?.deptId === filters.dept) &&
      (!q || t.title.toLowerCase().includes(q)));

    const cols = STATUSES.map((s) => {
      const items = list.filter((t) => t.status === s.id);
      return `<section class="col" data-drop="${s.id}">
        <h3>${s.label}<span class="count">${items.length}</span></h3>
        ${items.map(taskCard).join('') || '<p class="muted small empty">Không có việc</p>'}
      </section>`;
    }).join('');

    const form = state.projects.length ? `
      <form data-form="task" class="grid-form">
        <label class="span2">Tiêu đề công việc<input name="title" required maxlength="160" placeholder="VD: Xây dựng API đăng nhập"></label>
        <label>Dự án<select name="projectId" required>${projectOpts(filters.project || state.projects[0].id)}</select></label>
        <label>Giao cho<select name="assigneeId">${memberOpts('', 'Chưa giao')}</select></label>
        <label>Mức ưu tiên<select name="priority">${mapOpts(PRIORITIES, 'normal')}</select></label>
        <label>Hạn hoàn thành<input type="date" name="due"></label>
        <label>Ước lượng (giờ)<input type="number" name="estimate" min="0" step="0.5" value="4"></label>
        <label class="span2">Mô tả / tiêu chí hoàn thành<textarea name="desc" rows="2" maxlength="1000"></textarea></label>
        <div class="actions"><button type="submit" class="primary">Giao việc</button></div>
      </form>` : '<p class="muted">Hãy tạo ít nhất một dự án ở tab <a href="#projects">Dự án</a> trước khi giao việc.</p>';

    return `
      <details class="panel" open><summary>+ Giao việc mới</summary>${form}</details>
      <div class="toolbar">
        <input id="q" type="search" placeholder="Tìm công việc…" value="${esc(filters.q)}" aria-label="Tìm công việc">
        <select data-filter="project" aria-label="Lọc theo dự án">${projectOpts(filters.project, 'Tất cả dự án')}</select>
        <select data-filter="dept" aria-label="Lọc theo bộ phận">${deptOpts(filters.dept, 'Tất cả bộ phận')}</select>
        <select data-filter="assignee" aria-label="Lọc theo người thực hiện">${memberOpts(filters.assignee, 'Tất cả nhân sự')}</select>
      </div>
      <p class="muted small">Kéo thả thẻ giữa các cột hoặc đổi trạng thái/người thực hiện ngay trên thẻ.</p>
      <div class="board">${cols}</div>`;
  }

  // ---------- Màn hình: Dự án ----------
  function nextCode() {
    const nums = state.projects.map((p) => parseInt(String(p.code).replace(/\D/g, ''), 10)).filter(Number.isFinite);
    return `PRJ-${String((nums.length ? Math.max(...nums) : 0) + 1).padStart(3, '0')}`;
  }

  function viewProjects() {
    const rows = state.projects.map((p) => {
      const ts = state.tasks.filter((t) => t.projectId === p.id);
      const done = ts.filter((t) => t.status === 'done').length;
      const pct = ts.length ? Math.round((done / ts.length) * 100) : 0;
      return `<tr>
        <td><strong>${esc(p.code)}</strong> ${esc(p.name)}<div class="muted small">${esc(p.desc)}</div></td>
        <td>${esc(dept(p.deptId)?.name ?? '—')}</td>
        <td>${esc(memberName(p.ownerId))}</td>
        <td>${fmtDate(p.start)} → ${fmtDate(p.due)}</td>
        <td><div class="bar"><span style="width:${pct}%"></span></div><div class="small muted">${done}/${ts.length} việc · ${pct}%</div></td>
        <td><select data-change="project-status" data-id="${esc(p.id)}" aria-label="Trạng thái dự án">${mapOpts(PROJECT_STATUS, p.status)}</select></td>
        <td><button type="button" class="link danger" data-action="del-project" data-id="${esc(p.id)}">Xóa</button></td>
      </tr>`;
    }).join('');

    return `
      <details class="panel" open><summary>+ Tạo dự án mới</summary>
        <form data-form="project" class="grid-form">
          <label class="span2">Tên dự án<input name="name" required maxlength="160"></label>
          <label>Bộ phận chủ trì<select name="deptId">${deptOpts('d-pmo', 'Chưa chọn')}</select></label>
          <label>Quản lý dự án<select name="ownerId">${memberOpts('m-pm', 'Chưa chọn')}</select></label>
          <label>Ngày bắt đầu<input type="date" name="start" value="${todayIso()}"></label>
          <label>Hạn bàn giao<input type="date" name="due"></label>
          <label class="span2">Mô tả<input name="desc" maxlength="300"></label>
          <div class="actions"><button type="submit" class="primary">Tạo dự án</button></div>
        </form>
      </details>
      <div class="table-wrap"><table>
        <thead><tr><th>Dự án</th><th>Bộ phận</th><th>Quản lý</th><th>Thời gian</th><th>Tiến độ</th><th>Trạng thái</th><th></th></tr></thead>
        <tbody>${rows || '<tr><td colspan="7" class="muted">Chưa có dự án.</td></tr>'}</tbody>
      </table></div>`;
  }

  // ---------- Màn hình: Nhân sự ----------
  function viewPeople() {
    const rows = state.members.map((m) => `<tr>
      <td><strong>${esc(m.name)}</strong><div class="muted small">${esc(m.title)}</div></td>
      <td><select data-change="member-dept" data-id="${esc(m.id)}" aria-label="Bộ phận">${deptOpts(m.deptId, 'Chưa xếp')}</select></td>
      <td class="small">${esc(m.skills)}</td>
      <td><input class="num-in" type="number" min="0" max="50" value="${esc(m.capacity)}" data-change="member-capacity" data-id="${esc(m.id)}" aria-label="Sức chứa"></td>
      <td class="num">${openTasks(m.id).length}</td>
      <td><button type="button" class="link danger" data-action="del-member" data-id="${esc(m.id)}">Xóa</button></td>
    </tr>`).join('');

    return `
      <details class="panel" open><summary>+ Thêm nhân sự</summary>
        <form data-form="member" class="grid-form">
          <label>Họ và tên<input name="name" required maxlength="80"></label>
          <label>Chức danh<input name="title" maxlength="80" placeholder="VD: Backend Developer"></label>
          <label>Bộ phận<select name="deptId">${deptOpts(state.departments[0]?.id, 'Chưa xếp')}</select></label>
          <label>Kỹ năng<input name="skills" maxlength="200" placeholder="VD: React, Figma"></label>
          <label>Sức chứa (số việc mở tối đa)<input type="number" name="capacity" min="0" max="50" value="6"></label>
          <div class="actions"><button type="submit" class="primary">Thêm nhân sự</button></div>
        </form>
      </details>
      <div class="table-wrap"><table>
        <thead><tr><th>Nhân sự</th><th>Bộ phận</th><th>Kỹ năng</th><th>Sức chứa</th><th class="num">Việc mở</th><th></th></tr></thead>
        <tbody>${rows || '<tr><td colspan="6" class="muted">Chưa có nhân sự.</td></tr>'}</tbody>
      </table></div>`;
  }

  // ---------- Màn hình: Bộ phận ----------
  function viewDepts() {
    const cards = state.departments.map((d) => {
      const mem = state.members.filter((m) => m.deptId === d.id);
      const ids = new Set(mem.map((m) => m.id));
      const open = state.tasks.filter((t) => ids.has(t.assigneeId) && t.status !== 'done').length;
      const projs = state.projects.filter((p) => p.deptId === d.id).length;
      return `<article class="card">
        <h3>${esc(d.name)}</h3>
        <p class="muted small">${esc(d.desc)}</p>
        <div class="kv"><span>Nhân sự</span><b>${mem.length}</b><span>Việc đang mở</span><b>${open}</b><span>Dự án chủ trì</span><b>${projs}</b></div>
        <label class="small muted">Trưởng bộ phận
          <select data-change="dept-head" data-id="${esc(d.id)}">${selectOpts(mem.map((m) => ({ id: m.id, label: m.name })), d.head, 'Chưa bổ nhiệm')}</select>
        </label>
        <div class="small" style="margin-top:8px">
          <a href="#board" data-action="filter-dept" data-id="${esc(d.id)}">Xem việc của bộ phận</a> ·
          <button type="button" class="link danger" data-action="del-dept" data-id="${esc(d.id)}">Xóa bộ phận</button>
        </div>
      </article>`;
    }).join('');

    return `
      <details class="panel"><summary>+ Thêm bộ phận</summary>
        <form data-form="dept" class="grid-form">
          <label>Tên bộ phận<input name="name" required maxlength="80"></label>
          <label class="span2">Chức năng, nhiệm vụ<input name="desc" maxlength="200"></label>
          <div class="actions"><button type="submit" class="primary">Thêm bộ phận</button></div>
        </form>
      </details>
      <div class="cards">${cards || '<p class="muted">Chưa có bộ phận.</p>'}</div>`;
  }

  // ---------- Điều hướng & render ----------
  const VIEWS = { overview: viewOverview, board: viewBoard, projects: viewProjects, people: viewPeople, depts: viewDepts };

  function render() {
    const name = location.hash.slice(1);
    const key = VIEWS[name] ? name : 'overview';
    document.querySelectorAll('#nav a').forEach((a) => a.classList.toggle('active', a.getAttribute('href') === `#${key}`));
    const active = document.activeElement;
    const focusId = active && active.id;
    const caret = focusId && typeof active.selectionStart === 'number' ? active.selectionStart : null;
    $('#app').innerHTML = VIEWS[key]();
    if (focusId) {
      const el = document.getElementById(focusId);
      if (el) {
        el.focus();
        if (caret != null) { try { el.setSelectionRange(caret, caret); } catch (e) { /* bỏ qua */ } }
      }
    }
  }

  let toastTimer;
  function toast(msg) {
    const el = $('#toast');
    el.textContent = msg;
    el.classList.add('show');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => el.classList.remove('show'), 2600);
  }

  function exportJson() {
    const blob = new Blob([JSON.stringify(state, null, 2)], { type: 'application/json' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `projeck-${todayIso()}.json`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  }

  // ---------- Sự kiện ----------
  document.addEventListener('click', (e) => {
    const el = e.target.closest('[data-action]');
    if (!el) return;
    const id = el.dataset.id;
    switch (el.dataset.action) {
      case 'del-task':
        if (confirm('Xóa công việc này?')) {
          state.tasks = state.tasks.filter((t) => t.id !== id);
          commit('Đã xóa công việc');
        }
        break;
      case 'del-project':
        if (confirm('Xóa dự án và toàn bộ công việc thuộc dự án?')) {
          state.projects = state.projects.filter((p) => p.id !== id);
          state.tasks = state.tasks.filter((t) => t.projectId !== id);
          if (filters.project === id) filters.project = '';
          commit('Đã xóa dự án');
        }
        break;
      case 'del-member':
        if (confirm('Xóa nhân sự? Các việc đang giao cho người này sẽ chuyển về "Chưa giao".')) {
          state.members = state.members.filter((m) => m.id !== id);
          state.tasks.forEach((t) => { if (t.assigneeId === id) t.assigneeId = ''; });
          state.projects.forEach((p) => { if (p.ownerId === id) p.ownerId = ''; });
          state.departments.forEach((d) => { if (d.head === id) d.head = ''; });
          if (filters.assignee === id) filters.assignee = '';
          commit('Đã xóa nhân sự');
        }
        break;
      case 'del-dept':
        if (state.members.some((m) => m.deptId === id)) {
          toast('Hãy chuyển nhân sự sang bộ phận khác trước khi xóa');
        } else if (confirm('Xóa bộ phận này?')) {
          state.departments = state.departments.filter((d) => d.id !== id);
          state.projects.forEach((p) => { if (p.deptId === id) p.deptId = ''; });
          if (filters.dept === id) filters.dept = '';
          commit('Đã xóa bộ phận');
        }
        break;
      case 'filter-dept':
        Object.assign(filters, { project: '', assignee: '', q: '', dept: id });
        break; // liên kết #board sẽ tự render qua hashchange
      case 'export':
        exportJson();
        break;
      case 'reset':
        if (confirm('Thay toàn bộ dữ liệu hiện tại bằng dữ liệu mẫu? Nên Xuất JSON để sao lưu trước.')) {
          state = seed();
          Object.assign(filters, { project: '', assignee: '', dept: '', q: '' });
          commit('Đã khôi phục dữ liệu mẫu');
        }
        break;
      default:
    }
  });

  document.addEventListener('change', (e) => {
    const el = e.target;
    if (el.dataset.filter) {
      filters[el.dataset.filter] = el.value;
      render();
      return;
    }
    const id = el.dataset.id;
    switch (el.dataset.change) {
      case 'assignee': {
        const t = task(id);
        if (!t) return;
        t.assigneeId = el.value;
        commit(el.value ? `Đã giao "${t.title}" cho ${memberName(el.value)}` : 'Đã bỏ giao việc');
        break;
      }
      case 'status': { const t = task(id); if (t) { t.status = el.value; commit('Đã cập nhật trạng thái'); } break; }
      case 'project-status': { const p = project(id); if (p) { p.status = el.value; commit('Đã cập nhật dự án'); } break; }
      case 'member-dept': { const m = member(id); if (m) { m.deptId = el.value; commit('Đã chuyển bộ phận'); } break; }
      case 'member-capacity': { const m = member(id); if (m) { m.capacity = Math.max(0, Number(el.value) || 0); commit(); } break; }
      case 'dept-head': { const d = dept(id); if (d) { d.head = el.value; commit('Đã cập nhật trưởng bộ phận'); } break; }
      default:
    }
  });

  document.addEventListener('input', (e) => {
    if (e.target.id === 'q') { filters.q = e.target.value; render(); }
  });

  document.addEventListener('submit', (e) => {
    const form = e.target;
    const kind = form.dataset && form.dataset.form;
    if (!kind) return;
    e.preventDefault();
    const f = Object.fromEntries(new FormData(form));
    const text = (k) => String(f[k] ?? '').trim();
    if (kind === 'task') {
      if (!text('title') || !project(f.projectId)) return;
      state.tasks.push({
        id: uid('t'), projectId: f.projectId, title: text('title'), desc: text('desc'),
        assigneeId: f.assigneeId || '', priority: f.priority || 'normal', status: 'todo',
        due: f.due || '', estimate: Math.max(0, Number(f.estimate) || 0), createdAt: todayIso(),
      });
      commit(f.assigneeId ? `Đã giao việc cho ${memberName(f.assigneeId)}` : 'Đã tạo công việc (chưa giao)');
    } else if (kind === 'project') {
      if (!text('name')) return;
      state.projects.push({
        id: uid('p'), code: nextCode(), name: text('name'), deptId: f.deptId || '', ownerId: f.ownerId || '',
        start: f.start || '', due: f.due || '', status: 'active', desc: text('desc'),
      });
      commit('Đã tạo dự án');
    } else if (kind === 'member') {
      if (!text('name')) return;
      state.members.push({
        id: uid('m'), name: text('name'), title: text('title'), deptId: f.deptId || '',
        skills: text('skills'), capacity: Math.max(0, Number(f.capacity) || 0),
      });
      commit('Đã thêm nhân sự');
    } else if (kind === 'dept') {
      if (!text('name')) return;
      state.departments.push({ id: uid('d'), name: text('name'), desc: text('desc'), head: '' });
      commit('Đã thêm bộ phận');
    }
  });

  // Kéo thả thẻ công việc giữa các cột trạng thái
  document.addEventListener('dragstart', (e) => {
    const card = e.target.closest && e.target.closest('[data-task]');
    if (!card) return;
    e.dataTransfer.setData('text/plain', card.dataset.task);
    e.dataTransfer.effectAllowed = 'move';
  });
  document.addEventListener('dragover', (e) => {
    if (e.target.closest && e.target.closest('[data-drop]')) e.preventDefault();
  });
  document.addEventListener('drop', (e) => {
    const col = e.target.closest && e.target.closest('[data-drop]');
    if (!col) return;
    e.preventDefault();
    const t = task(e.dataTransfer.getData('text/plain'));
    if (t && t.status !== col.dataset.drop) {
      t.status = col.dataset.drop;
      commit('Đã chuyển trạng thái');
    }
  });

  $('#importFile').addEventListener('change', async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    try {
      const data = JSON.parse(await file.text());
      if (!isValidData(data)) throw new Error('invalid');
      state = data;
      Object.assign(filters, { project: '', assignee: '', dept: '', q: '' });
      commit('Đã nhập dữ liệu');
    } catch (err) {
      toast('File JSON không hợp lệ');
    }
    e.target.value = '';
  });

  window.addEventListener('hashchange', render);
  if (!location.hash) history.replaceState(null, '', '#overview');
  render();
})();
