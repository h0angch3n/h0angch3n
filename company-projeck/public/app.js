/* Projeck — giao diện quản lý dự án & giao việc của Công ty Cổ phần Dịch vụ Dev.
 * Dữ liệu dùng chung nằm trên máy chủ (server.py); trang này chỉ hiển thị và gửi thao tác. */
(() => {
  'use strict';

  const STATUSES = [
    { id: 'todo', label: 'Chờ làm' },
    { id: 'doing', label: 'Đang làm' },
    { id: 'review', label: 'Chờ duyệt' },
    { id: 'done', label: 'Hoàn thành' },
  ];
  const PRIORITIES = { urgent: 'Khẩn', high: 'Cao', normal: 'Thường', low: 'Thấp' };
  const PRI_RANK = { urgent: 0, high: 1, normal: 2, low: 3 };
  const PROJECT_STATUS = { active: 'Đang chạy', paused: 'Tạm dừng', closed: 'Đã đóng' };
  const ROLES = { admin: 'Quản trị / Tổng Giám đốc', pm: 'Quản lý dự án', lead: 'Trưởng bộ phận', staff: 'Nhân viên' };
  const GOVERNANCE = ['Hội đồng quản trị', 'Ban Kiểm soát', 'Ban Tổng Giám đốc'];

  let S = null; // dữ liệu từ máy chủ
  let me = null;
  let lastJson = '';
  const filters = { project: '', assignee: '', dept: '', q: '' };

  // ---------- Tiện ích ----------
  const $ = (sel) => document.querySelector(sel);
  const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const pad = (n) => String(n).padStart(2, '0');
  const todayIso = () => { const d = new Date(); return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`; };
  const fmtDate = (s) => (s ? s.split('-').reverse().join('/') : '—');
  const fmtTime = (s) => (s ? `${fmtDate(s.slice(0, 10))} ${s.slice(11, 16)}` : '');
  const isOverdue = (t) => Boolean(t.due) && t.status !== 'done' && t.due < todayIso();
  const num = (v) => (v === '' || v == null ? null : Number(v));

  async function api(method, path, body) {
    const opt = { method, credentials: 'same-origin', headers: {} };
    if (method !== 'GET') {
      opt.headers['Content-Type'] = 'application/json';
      opt.body = JSON.stringify(body || {});
    }
    let res;
    try { res = await fetch(path, opt); } catch (e) { throw new Error('Mất kết nối tới máy chủ Projeck'); }
    let data = {};
    try { data = await res.json(); } catch (e) { /* phản hồi rỗng */ }
    if (res.status === 401 && !path.startsWith('/api/login') && !path.startsWith('/api/me/')) {
      showLogin(false);
      throw new Error(data.error || 'Phiên đăng nhập đã hết');
    }
    if (!res.ok) throw new Error(data.error || `Lỗi ${res.status}`);
    return data;
  }

  let toastTimer;
  function toast(msg, isError) {
    const el = $('#toast');
    el.textContent = msg;
    el.style.background = isError ? 'var(--danger)' : '';
    el.classList.add('show');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => el.classList.remove('show'), isError ? 4000 : 2600);
  }

  async function refresh() {
    S = await api('GET', '/api/state');
    me = S.me;
    lastJson = JSON.stringify(S);
    render();
  }

  async function act(fn, msg) {
    try {
      await fn();
      await refresh();
      if (msg) toast(msg);
      return true;
    } catch (e) {
      toast(e.message, true);
      return false;
    }
  }

  // ---------- Tra cứu ----------
  const byId = (list, id) => list.find((x) => x.id === id);
  const dept = (id) => byId(S.departments, id);
  const user = (id) => byId(S.users, id);
  const project = (id) => byId(S.projects, id);
  const task = (id) => byId(S.tasks, id);
  const userName = (id) => user(id)?.name ?? 'Chưa giao';
  const activeUsers = () => S.users.filter((u) => u.active);
  const openTasks = (uid) => S.tasks.filter((t) => t.assignee_id === uid && t.status !== 'done');

  // ---------- Quyền (máy chủ kiểm tra lại toàn bộ) ----------
  const isAdmin = () => me.role === 'admin';
  const isMgr = () => me.role === 'admin' || me.role === 'pm';
  function canAssignTo(u) {
    if (isMgr()) return true;
    if (!u) return me.role === 'lead';
    if (me.role === 'lead') return u.dept_id != null && u.dept_id === me.dept_id;
    return u.id === me.id;
  }
  function canEditTask(t) {
    if (isMgr()) return true;
    const a = user(t.assignee_id);
    if (me.role === 'lead') return t.creator_id === me.id || t.assignee_id == null || (a && a.dept_id === me.dept_id);
    return t.assignee_id === me.id || t.creator_id === me.id;
  }
  const fullEdit = (t) => canEditTask(t) && (me.role !== 'staff' || t.creator_id === me.id);
  const canDeleteTask = (t) => isMgr() || t.creator_id === me.id;
  const canMarkDone = (t) => me.role !== 'staff' || t.creator_id === me.id;
  function isReviewer(t) {
    if (t.status !== 'review' || t.assignee_id === me.id) return false;
    if (t.creator_id === me.id) return true;
    if (isMgr()) return project(t.project_id)?.owner_id === me.id;
    if (me.role === 'lead') return user(t.assignee_id)?.dept_id === me.dept_id;
    return false;
  }

  // ---------- Ô chọn ----------
  function selectOpts(list, selected, emptyLabel) {
    const empty = emptyLabel != null ? `<option value="">${esc(emptyLabel)}</option>` : '';
    return empty + list.map((o) =>
      `<option value="${esc(o.id)}"${o.id === selected ? ' selected' : ''}>${esc(o.label)}</option>`).join('');
  }
  const userLabel = (u) => { const d = dept(u.dept_id); return d ? `${u.name} — ${d.name}` : u.name; };
  const userOpts = (list, sel, empty) => selectOpts(list.map((u) => ({ id: u.id, label: userLabel(u) })), sel, empty);
  function assigneeOpts(sel) {
    const list = activeUsers().filter(canAssignTo);
    const cur = user(sel);
    if (cur && !list.includes(cur)) list.unshift(cur);
    return userOpts(list, sel, canAssignTo(null) || sel == null ? 'Chưa giao' : null);
  }
  const projectOpts = (sel, empty, openOnly) => selectOpts(
    S.projects.filter((p) => !openOnly || p.status !== 'closed' || p.id === sel)
      .map((p) => ({ id: p.id, label: `${p.code} · ${p.name}` })), sel, empty);
  const deptOpts = (sel, empty) => selectOpts(S.departments.map((d) => ({ id: d.id, label: d.name })), sel, empty);
  const mapOpts = (obj, sel) => Object.entries(obj)
    .map(([k, v]) => `<option value="${k}"${k === sel ? ' selected' : ''}>${esc(v)}</option>`).join('');
  const statusOpts = (t) => STATUSES.filter((s) => s.id !== 'done' || canMarkDone(t) || t.status === 'done')
    .map((s) => `<option value="${s.id}"${s.id === t.status ? ' selected' : ''}>${s.label}</option>`).join('');
  const badgePri = (p) => `<span class="badge pri-${esc(p)}">${esc(PRIORITIES[p] || p)}</span>`;
  const dis = (ok) => (ok ? '' : ' disabled');

  // ---------- Đăng nhập / thiết lập lần đầu ----------
  function showLogin(needsSetup, company) {
    S = null;
    me = null;
    document.body.classList.add('logged-out');
    if (company) setCompany(company);
    $('#notif').hidden = true;
    if ($('#dlg').open) $('#dlg').close();
    $('#app').innerHTML = needsSetup ? `
      <section class="panel auth">
        <h2>Thiết lập lần đầu</h2>
        <p class="muted">Tạo tài khoản quản trị (Tổng Giám đốc). Hệ thống tạo sẵn cơ cấu công ty cổ phần 18 bộ phận
          và dự án <b>"Triển khai Projeck"</b> liệt kê từng bước tiếp theo.</p>
        <form data-form="setup" class="stack">
          <label>Tên công ty<input name="company" maxlength="160" value="${esc(company || 'Công ty Cổ phần Dịch vụ Dev')}" required></label>
          <label>Họ và tên<input name="name" maxlength="80" required autocomplete="name"></label>
          <label>Tên đăng nhập (chữ không dấu, số, . _ -)<input name="username" maxlength="32" required pattern="[A-Za-z0-9._\\-]{2,32}" autocomplete="username"></label>
          <label>Mật khẩu (tối thiểu 6 ký tự)<input name="password" type="password" minlength="6" required autocomplete="new-password"></label>
          <label>Nhập lại mật khẩu<input name="password2" type="password" minlength="6" required autocomplete="new-password"></label>
          <button class="primary" type="submit">Tạo tài khoản và bắt đầu</button>
        </form>
      </section>` : `
      <section class="panel auth">
        <h2>Đăng nhập</h2>
        <form data-form="login" class="stack">
          <label>Tên đăng nhập<input name="username" required autocomplete="username" autofocus></label>
          <label>Mật khẩu<input name="password" type="password" required autocomplete="current-password"></label>
          <button class="primary" type="submit">Đăng nhập</button>
        </form>
        <p class="muted small">Quên mật khẩu? Nhờ quản trị đặt lại trong tab Nhân sự.</p>
      </section>`;
  }

  function setCompany(name) {
    $('#company').textContent = name;
    document.title = `Projeck — ${name}`;
  }

  function renderUserbox() {
    $('#userbox').innerHTML = `
      <button type="button" class="bell" data-action="notif" aria-label="Thông báo">Thông báo${S.unread ? ` <span class="dot">${S.unread}</span>` : ''}</button>
      <div class="userchip"><b>${esc(me.name)}</b><span class="muted">${esc(ROLES[me.role])}</span></div>
      <button type="button" data-action="password">Đổi mật khẩu</button>
      ${isAdmin() ? '<button type="button" data-action="export">Xuất dữ liệu</button>' : ''}
      <button type="button" data-action="logout">Đăng xuất</button>`;
  }

  // ---------- Thẻ công việc ----------
  function taskCard(t) {
    const p = project(t.project_id);
    const late = isOverdue(t);
    const editable = canEditTask(t);
    const assignee = fullEdit(t)
      ? `<select data-change="assignee" data-id="${t.id}" aria-label="Người thực hiện">${assigneeOpts(t.assignee_id)}</select>`
      : `<span class="small">${esc(userName(t.assignee_id))}</span>`;
    return `<article class="card${late ? ' overdue' : ''}"${editable ? ' draggable="true"' : ''} data-task="${t.id}">
      <div class="card-top">${badgePri(t.priority)}<span class="muted">${esc(p?.code ?? '')}</span></div>
      <button type="button" class="title-btn" data-action="open-task" data-id="${t.id}">${esc(t.title)}</button>
      <div class="small ${late ? 'late' : 'muted'}">${t.due ? `Hạn ${fmtDate(t.due)}${late ? ' · quá hạn' : ''}` : 'Không đặt hạn'} · ${esc(t.estimate || 0)}h</div>
      <div class="row">
        ${assignee}
        <select data-change="status" data-id="${t.id}" aria-label="Trạng thái"${dis(editable)}>${statusOpts(t)}</select>
      </div>
    </article>`;
  }
  const sortTasks = (list) => list.slice().sort((a, b) =>
    (isOverdue(b) - isOverdue(a)) || (PRI_RANK[a.priority] - PRI_RANK[b.priority]) ||
    (a.due || '9999').localeCompare(b.due || '9999'));

  // ---------- Việc của tôi ----------
  function viewMine() {
    const mine = sortTasks(S.tasks.filter((t) => t.assignee_id === me.id && t.status !== 'done'));
    const review = sortTasks(S.tasks.filter(isReviewer));
    const given = sortTasks(S.tasks.filter((t) => t.creator_id === me.id && t.assignee_id !== me.id
      && t.status !== 'done' && t.status !== 'review'));
    const late = mine.filter(isOverdue).length;
    const section = (title, list, empty) => `
      <h2>${title} <span class="count">${list.length}</span></h2>
      ${list.length ? `<div class="cards">${list.map(taskCard).join('')}</div>` : `<p class="muted">${empty}</p>`}`;
    return `
      <div class="panel hello">
        <div><h2>Chào ${esc(me.name)}</h2>
          <div class="muted">${esc(ROLES[me.role])}${dept(me.dept_id) ? ` · ${esc(dept(me.dept_id).name)}` : ''} —
          bạn có <b>${mine.length}</b> việc đang mở${late ? `, <b class="late">${late} quá hạn</b>` : ''}.</div></div>
        <a class="btn primary" href="#board">+ Giao việc mới</a>
      </div>
      ${section('Việc tôi cần làm', mine, 'Không có việc nào đang chờ bạn.')}
      ${review.length || me.role !== 'staff' ? section('Chờ tôi duyệt', review, 'Không có việc chờ duyệt.') : ''}
      ${given.length ? section('Việc tôi đã giao (đang làm)', given, '') : ''}
      <p class="muted small">Quy ước: bắt đầu làm → <b>Đang làm</b>; làm xong → <b>Chờ duyệt</b>; vướng mắc → mở việc và viết bình luận.</p>`;
  }

  // ---------- Tổng quan ----------
  function viewOverview() {
    const all = S.tasks;
    const count = (s) => all.filter((t) => t.status === s).length;
    const overdue = sortTasks(all.filter(isOverdue));
    const unassigned = all.filter((t) => t.assignee_id == null && t.status !== 'done');
    const pct = all.length ? Math.round((count('done') / all.length) * 100) : 0;
    const stats = [
      ['Tổng công việc', all.length], ['Đang làm', count('doing')], ['Chờ duyệt', count('review')],
      ['Quá hạn', overdue.length, overdue.length ? 'late' : ''], ['Chưa giao', unassigned.length],
      ['Hoàn thành', `${pct}%`],
    ].map(([label, val, cls = '']) =>
      `<div class="stat ${cls}"><div class="val">${val}</div><div class="muted">${label}</div></div>`).join('');

    const rows = activeUsers().map((u) => {
      const open = openTasks(u.id);
      const late = open.filter(isOverdue).length;
      const ratio = u.capacity ? Math.round((open.length / u.capacity) * 100) : (open.length ? 100 : 0);
      return `<tr>
        <td><strong>${esc(u.name)}</strong><div class="muted small">${esc(u.title)}</div></td>
        <td>${esc(dept(u.dept_id)?.name ?? '—')}</td>
        <td class="num">${open.length} / ${esc(u.capacity)}</td>
        <td><div class="bar" title="${ratio}% sức chứa"><span class="${ratio >= 100 ? 'over' : ''}" style="width:${Math.min(ratio, 100)}%"></span></div></td>
        <td class="num ${late ? 'late' : ''}">${late}</td>
      </tr>`;
    }).join('');

    const lateList = overdue.length
      ? `<ul class="list">${overdue.map((t) => `<li><button type="button" class="link" data-action="open-task" data-id="${t.id}"><strong>${esc(t.title)}</strong></button> — ${esc(userName(t.assignee_id))}, hạn ${fmtDate(t.due)}</li>`).join('')}</ul>`
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

  // ---------- Công việc (Kanban + giao việc) ----------
  function viewBoard() {
    const q = filters.q.trim().toLowerCase();
    const list = S.tasks.filter((t) =>
      (!filters.project || t.project_id === num(filters.project)) &&
      (!filters.assignee || t.assignee_id === num(filters.assignee)) &&
      (!filters.dept || user(t.assignee_id)?.dept_id === num(filters.dept)) &&
      (!q || t.title.toLowerCase().includes(q)));

    const cols = STATUSES.map((s) => {
      const items = sortTasks(list.filter((t) => t.status === s.id));
      return `<section class="col" data-drop="${s.id}">
        <h3>${s.label}<span class="count">${items.length}</span></h3>
        ${items.map(taskCard).join('') || '<p class="muted small empty">Không có việc</p>'}
      </section>`;
    }).join('');

    const openProjects = S.projects.filter((p) => p.status !== 'closed');
    const hint = me.role === 'staff' ? '<p class="muted small span-all">Nhân viên tự ghi nhận việc của mình; việc cho người khác do trưởng bộ phận hoặc quản lý giao.</p>'
      : me.role === 'lead' ? '<p class="muted small span-all">Trưởng bộ phận giao việc cho nhân sự trong bộ phận của mình.</p>' : '';
    const form = openProjects.length ? `
      <form data-form="task" class="grid-form">
        ${hint}
        <label class="span2">Tiêu đề công việc<input name="title" required maxlength="160" placeholder="VD: Xây dựng API đăng nhập"></label>
        <label>Dự án<select name="project_id" required>${projectOpts(num(filters.project) || openProjects[0].id, null, true)}</select></label>
        <label>Giao cho<select name="assignee_id">${assigneeOpts(me.role === 'staff' ? me.id : null)}</select></label>
        <label>Mức ưu tiên<select name="priority">${mapOpts(PRIORITIES, 'normal')}</select></label>
        <label>Hạn hoàn thành<input type="date" name="due"></label>
        <label>Ước lượng (giờ)<input type="number" name="estimate" min="0" max="1000" step="0.5" value="4"></label>
        <label class="span2">Mô tả / tiêu chí hoàn thành<textarea name="descr" rows="2" maxlength="2000"></textarea></label>
        <div class="actions"><button type="submit" class="primary">Giao việc</button></div>
      </form>` : `<p class="muted">Chưa có dự án đang chạy. ${isMgr() ? 'Hãy tạo dự án ở tab <a href="#projects">Dự án</a>.' : 'Nhờ quản lý dự án tạo dự án trước.'}</p>`;

    return `
      <details class="panel" open><summary>+ Giao việc mới</summary>${form}</details>
      <div class="toolbar">
        <input id="q" type="search" placeholder="Tìm công việc…" value="${esc(filters.q)}" aria-label="Tìm công việc">
        <select data-filter="project" aria-label="Lọc theo dự án">${projectOpts(num(filters.project), 'Tất cả dự án')}</select>
        <select data-filter="dept" aria-label="Lọc theo bộ phận">${deptOpts(num(filters.dept), 'Tất cả bộ phận')}</select>
        <select data-filter="assignee" aria-label="Lọc theo người thực hiện">${userOpts(activeUsers(), num(filters.assignee), 'Tất cả nhân sự')}</select>
      </div>
      <p class="muted small">Bấm vào tên việc để xem chi tiết, bình luận và lịch sử. Kéo thả thẻ để đổi trạng thái.</p>
      <div class="board">${cols}</div>`;
  }

  // ---------- Chi tiết công việc ----------
  async function openTask(id) {
    const t = task(id);
    if (!t) return;
    let acts = [];
    try { acts = (await api('GET', `/api/tasks/${id}/activity`)).items; } catch (e) { toast(e.message, true); }
    const full = fullEdit(t);
    const can = canEditTask(t);
    const p = project(t.project_id);
    $('#dlg').innerHTML = `
      <form data-form="task-edit" data-id="${t.id}" class="grid-form">
        <div class="dlg-head span-all"><h3>${esc(p?.code ?? '')} · Việc #${t.id}</h3>
          <button type="button" class="link" data-action="close-dlg">Đóng ✕</button></div>
        <label class="span-all">Tiêu đề<input name="title" value="${esc(t.title)}" required maxlength="160"${dis(full)}></label>
        <label>Dự án<select name="project_id"${dis(full)}>${projectOpts(t.project_id, null, true)}</select></label>
        <label>Giao cho<select name="assignee_id"${dis(full)}>${assigneeOpts(t.assignee_id)}</select></label>
        <label>Trạng thái<select name="status"${dis(can)}>${statusOpts(t)}</select></label>
        <label>Mức ưu tiên<select name="priority"${dis(full)}>${mapOpts(PRIORITIES, t.priority)}</select></label>
        <label>Hạn hoàn thành<input type="date" name="due" value="${esc(t.due)}"${dis(full)}></label>
        <label>Ước lượng (giờ)<input type="number" name="estimate" min="0" max="1000" step="0.5" value="${esc(t.estimate)}"${dis(full)}></label>
        <label class="span-all">Mô tả / tiêu chí hoàn thành<textarea name="descr" rows="4" maxlength="2000"${dis(full)}>${esc(t.descr)}</textarea></label>
        <div class="span-all small muted">Người giao: ${esc(userName(t.creator_id))} · Tạo lúc ${fmtTime(t.created_at)} · Cập nhật ${fmtTime(t.updated_at)}</div>
        <div class="span-all actions" style="gap:8px">
          ${canDeleteTask(t) ? `<button type="button" class="danger" data-action="del-task" data-id="${t.id}">Xóa việc</button>` : ''}
          ${can ? '<button class="primary" type="submit">Lưu thay đổi</button>' : '<span class="muted small">Bạn chỉ xem được việc này.</span>'}
        </div>
      </form>
      <h3 style="margin-top:16px">Trao đổi &amp; lịch sử</h3>
      <ul class="activity">${acts.map((a) => `<li class="${esc(a.kind)}"><b>${esc(a.user_name || 'Hệ thống')}</b>
        <span class="muted small">${fmtTime(a.created_at)}</span><div>${esc(a.body)}</div></li>`).join('') || '<li class="muted">Chưa có trao đổi.</li>'}</ul>
      <form data-form="comment" data-id="${t.id}" class="comment-form">
        <textarea name="body" rows="2" required maxlength="2000" placeholder="Báo tiến độ, hỏi thêm, ghi chú khi duyệt…" aria-label="Bình luận"></textarea>
        <button class="primary" type="submit">Gửi</button>
      </form>`;
    if (!$('#dlg').open) $('#dlg').showModal();
  }

  // ---------- Dự án ----------
  function viewProjects() {
    const rows = S.projects.map((p) => {
      const ts = S.tasks.filter((t) => t.project_id === p.id);
      const done = ts.filter((t) => t.status === 'done').length;
      const pct = ts.length ? Math.round((done / ts.length) * 100) : 0;
      return `<tr>
        <td><strong>${esc(p.code)}</strong> ${esc(p.name)}<div class="muted small">${esc(p.descr)}</div></td>
        <td>${esc(dept(p.dept_id)?.name ?? '—')}</td>
        <td>${isMgr() ? `<select data-change="project-owner" data-id="${p.id}" aria-label="Quản lý dự án">${userOpts(activeUsers(), p.owner_id, 'Chưa chọn')}</select>` : esc(user(p.owner_id)?.name ?? '—')}</td>
        <td>${fmtDate(p.start)} → ${fmtDate(p.due)}</td>
        <td><div class="bar"><span style="width:${pct}%"></span></div><div class="small muted">${done}/${ts.length} việc · ${pct}%</div></td>
        <td><select data-change="project-status" data-id="${p.id}" aria-label="Trạng thái dự án"${dis(isMgr())}>${mapOpts(PROJECT_STATUS, p.status)}</select></td>
        <td>${isMgr() ? `<button type="button" class="link danger" data-action="del-project" data-id="${p.id}">Xóa</button>` : ''}</td>
      </tr>`;
    }).join('');
    const pmo = S.departments.find((d) => d.name.startsWith('Quản lý dự án'));
    const form = isMgr() ? `
      <details class="panel" open><summary>+ Tạo dự án mới</summary>
        <form data-form="project" class="grid-form">
          <label class="span2">Tên dự án<input name="name" required maxlength="160"></label>
          <label>Bộ phận chủ trì<select name="dept_id">${deptOpts(pmo?.id, 'Chưa chọn')}</select></label>
          <label>Quản lý dự án<select name="owner_id">${userOpts(activeUsers(), me.id, 'Chưa chọn')}</select></label>
          <label>Ngày bắt đầu<input type="date" name="start" value="${todayIso()}"></label>
          <label>Hạn bàn giao<input type="date" name="due"></label>
          <label class="span2">Mô tả / khách hàng / hợp đồng<input name="descr" maxlength="300"></label>
          <div class="actions"><button type="submit" class="primary">Tạo dự án</button></div>
        </form>
      </details>` : '<p class="muted small">Chỉ Quản trị và Quản lý dự án được tạo, sửa dự án.</p>';
    return `${form}
      <div class="table-wrap"><table>
        <thead><tr><th>Dự án</th><th>Bộ phận</th><th>Quản lý</th><th>Thời gian</th><th>Tiến độ</th><th>Trạng thái</th><th></th></tr></thead>
        <tbody>${rows || '<tr><td colspan="7" class="muted">Chưa có dự án.</td></tr>'}</tbody>
      </table></div>`;
  }

  // ---------- Nhân sự ----------
  function viewPeople() {
    const admin = isAdmin();
    const row = (u) => `<tr>
      <td><strong>${esc(u.name)}</strong><div class="muted small">${esc(u.title)} · @${esc(u.username)}</div></td>
      <td>${admin ? `<select data-change="user-dept" data-id="${u.id}" aria-label="Bộ phận">${deptOpts(u.dept_id, 'Chưa xếp')}</select>` : esc(dept(u.dept_id)?.name ?? '—')}</td>
      <td>${admin ? `<select data-change="user-role" data-id="${u.id}" aria-label="Vai trò">${mapOpts(ROLES, u.role)}</select>` : esc(ROLES[u.role])}</td>
      <td class="small">${esc(u.skills)}</td>
      <td>${admin ? `<input class="num-in" type="number" min="0" max="50" value="${esc(u.capacity)}" data-change="user-capacity" data-id="${u.id}" aria-label="Sức chứa">` : esc(u.capacity)}</td>
      <td class="num">${openTasks(u.id).length}</td>
      <td>${admin ? `<button type="button" class="link" data-action="reset-pw" data-id="${u.id}">Đặt lại MK</button>
        ${u.id !== me.id ? ` · <button type="button" class="link danger" data-action="deactivate" data-id="${u.id}">Cho nghỉ</button>` : ''}` : ''}</td>
    </tr>`;
    const inactive = S.users.filter((u) => !u.active);
    const form = admin ? `
      <details class="panel" open><summary>+ Thêm nhân sự (tạo tài khoản)</summary>
        <form data-form="user" class="grid-form">
          <label>Họ và tên<input name="name" required maxlength="80"></label>
          <label>Tên đăng nhập<input name="username" required maxlength="32" pattern="[A-Za-z0-9._\\-]{2,32}" placeholder="vd: an.nguyen"></label>
          <label>Mật khẩu tạm (≥ 6 ký tự)<input name="password" required minlength="6"></label>
          <label>Bộ phận<select name="dept_id">${deptOpts(null, 'Chưa xếp')}</select></label>
          <label>Vai trò<select name="role">${mapOpts(ROLES, 'staff')}</select></label>
          <label>Chức danh<input name="title" maxlength="80" placeholder="VD: Backend Developer"></label>
          <label>Kỹ năng<input name="skills" maxlength="200" placeholder="VD: React, Figma"></label>
          <label>Sức chứa (số việc mở tối đa)<input type="number" name="capacity" min="0" max="50" value="6"></label>
          <div class="actions"><button type="submit" class="primary">Tạo tài khoản</button></div>
        </form>
      </details>` : '<p class="muted small">Chỉ Quản trị được thêm nhân sự và phân vai trò.</p>';
    return `${form}
      <div class="table-wrap"><table>
        <thead><tr><th>Nhân sự</th><th>Bộ phận</th><th>Vai trò</th><th>Kỹ năng</th><th>Sức chứa</th><th class="num">Việc mở</th><th></th></tr></thead>
        <tbody>${activeUsers().map(row).join('') || '<tr><td colspan="7" class="muted">Chưa có nhân sự.</td></tr>'}</tbody>
      </table></div>
      ${inactive.length ? `<details class="panel" style="margin-top:14px"><summary>Đã nghỉ (${inactive.length})</summary>
        <ul class="list">${inactive.map((u) => `<li>${esc(u.name)} <span class="muted">@${esc(u.username)}</span>
          ${admin ? `<button type="button" class="link" data-action="reactivate" data-id="${u.id}">Cho làm lại</button>` : ''}</li>`).join('')}</ul></details>` : ''}`;
  }

  // ---------- Cơ cấu tổ chức ----------
  function viewDepts() {
    const admin = isAdmin();
    const gov = GOVERNANCE.map((n) => S.departments.find((d) => d.name === n)).filter(Boolean);
    const ops = S.departments.filter((d) => !gov.includes(d));
    const node = (d) => `<span class="node">${esc(d.name)}</span>`;
    const hdqt = gov.find((d) => d.name === 'Hội đồng quản trị');
    const bks = gov.find((d) => d.name === 'Ban Kiểm soát');
    const btgd = gov.find((d) => d.name === 'Ban Tổng Giám đốc');
    const org = `<div class="org" aria-label="Sơ đồ tổ chức">
      <span class="node top">Đại hội đồng cổ đông</span><span class="arrow">↓</span>
      <div class="row">${hdqt ? node(hdqt) : ''}${bks ? node(bks) : ''}</div><span class="arrow">↓</span>
      ${btgd ? `${node(btgd)}<span class="arrow">↓</span>` : ''}
      <div class="row">${ops.map(node).join('')}</div></div>`;

    const cards = S.departments.map((d) => {
      const mem = activeUsers().filter((u) => u.dept_id === d.id);
      const ids = new Set(mem.map((u) => u.id));
      const open = S.tasks.filter((t) => ids.has(t.assignee_id) && t.status !== 'done').length;
      const projs = S.projects.filter((p) => p.dept_id === d.id).length;
      return `<article class="card">
        <h3>${esc(d.name)}</h3>
        <p class="muted small">${esc(d.descr)}</p>
        <div class="kv"><span>Nhân sự</span><b>${mem.length}</b><span>Việc đang mở</span><b>${open}</b><span>Dự án chủ trì</span><b>${projs}</b></div>
        <label class="small muted">Trưởng bộ phận
          ${admin ? `<select data-change="dept-head" data-id="${d.id}">${selectOpts(mem.map((u) => ({ id: u.id, label: u.name })), d.head_id, 'Chưa bổ nhiệm')}</select>`
            : `<div>${esc(user(d.head_id)?.name ?? 'Chưa bổ nhiệm')}</div>`}
        </label>
        <div class="small" style="margin-top:8px">
          <a href="#board" data-action="filter-dept" data-id="${d.id}">Xem việc của bộ phận</a>
          ${admin ? ` · <button type="button" class="link" data-action="edit-dept" data-id="${d.id}">Sửa</button>
            · <button type="button" class="link danger" data-action="del-dept" data-id="${d.id}">Xóa</button>` : ''}
        </div>
      </article>`;
    }).join('');

    return `
      ${admin ? `<details class="panel"><summary>Thông tin công ty</summary>
        <form data-form="company" class="grid-form">
          <label class="span2">Tên công ty<input name="company" required maxlength="160" value="${esc(S.company)}"></label>
          <div class="actions"><button type="submit" class="primary">Lưu</button></div>
        </form></details>
      <details class="panel"><summary>+ Thêm bộ phận</summary>
        <form data-form="dept" class="grid-form">
          <label>Tên bộ phận<input name="name" required maxlength="80"></label>
          <label class="span2">Chức năng, nhiệm vụ<input name="descr" maxlength="200"></label>
          <div class="actions"><button type="submit" class="primary">Thêm bộ phận</button></div>
        </form>
      </details>` : ''}
      <h2>Sơ đồ tổ chức — ${esc(S.company)}</h2>
      ${org}
      <div class="cards">${cards || '<p class="muted">Chưa có bộ phận.</p>'}</div>`;
  }

  // ---------- Điều hướng & render ----------
  const VIEWS = { mine: viewMine, overview: viewOverview, board: viewBoard, projects: viewProjects, people: viewPeople, depts: viewDepts };

  function render() {
    if (!S) return;
    document.body.classList.remove('logged-out');
    setCompany(S.company);
    renderUserbox();
    const name = location.hash.slice(1);
    const key = VIEWS[name] ? name : 'mine';
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

  async function showNotifications() {
    const panel = $('#notif');
    if (!panel.hidden) { panel.hidden = true; return; }
    try {
      const { items } = await api('GET', '/api/notifications');
      panel.innerHTML = `<div class="dlg-head" style="padding:4px 8px"><b>Thông báo</b>
          <button type="button" class="link" data-action="close-notif">Đóng ✕</button></div>` + (items.length ? items.map((n) => `
        <button type="button" class="item${n.is_read ? '' : ' unread'}" data-action="open-task" data-id="${n.task_id ?? ''}">
          ${esc(n.body)}<div class="muted small">${fmtTime(n.created_at)}</div></button>`).join('')
        : '<p class="muted" style="padding:8px">Chưa có thông báo.</p>');
      // Đặt ngay dưới thanh tiêu đề (trên điện thoại thanh này cao hơn) để không che các nút.
      panel.style.top = `${Math.round($('.topbar').getBoundingClientRect().bottom) + 6}px`;
      panel.hidden = false;
      if (S.unread) { await api('POST', '/api/notifications/read'); S.unread = 0; renderUserbox(); }
    } catch (e) { toast(e.message, true); }
  }

  function passwordDialog() {
    $('#dlg').innerHTML = `
      <form data-form="password" class="stack">
        <div class="dlg-head"><h3>Đổi mật khẩu</h3><button type="button" class="link" data-action="close-dlg">Đóng ✕</button></div>
        <label>Mật khẩu hiện tại<input type="password" name="old_password" required autocomplete="current-password"></label>
        <label>Mật khẩu mới (≥ 6 ký tự)<input type="password" name="new_password" minlength="6" required autocomplete="new-password"></label>
        <label>Nhập lại mật khẩu mới<input type="password" name="new_password2" minlength="6" required autocomplete="new-password"></label>
        <button class="primary" type="submit">Đổi mật khẩu</button>
      </form>`;
    $('#dlg').showModal();
  }

  async function exportData() {
    try {
      const data = await api('GET', '/api/export');
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = `projeck-${todayIso()}.json`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      setTimeout(() => URL.revokeObjectURL(a.href), 1000);
    } catch (e) { toast(e.message, true); }
  }

  // ---------- Sự kiện ----------
  document.addEventListener('click', async (e) => {
    const panel = $('#notif');
    if (!panel.hidden && !e.target.closest('#notif') && !e.target.closest('[data-action="notif"]')) panel.hidden = true;
    const el = e.target.closest('[data-action]');
    if (!el) return;
    const id = num(el.dataset.id);
    switch (el.dataset.action) {
      case 'open-task':
        panel.hidden = true;
        if (id) openTask(id);
        break;
      case 'close-dlg':
        $('#dlg').close();
        break;
      case 'close-notif':
        panel.hidden = true;
        break;
      case 'notif':
        showNotifications();
        break;
      case 'password':
        passwordDialog();
        break;
      case 'export':
        exportData();
        break;
      case 'logout':
        try { await api('POST', '/api/logout'); } catch (err) { /* vẫn thoát */ }
        showLogin(false);
        break;
      case 'del-task':
        if (confirm('Xóa công việc này cùng toàn bộ bình luận?')) {
          if (await act(() => api('DELETE', `/api/tasks/${id}`), 'Đã xóa công việc')) $('#dlg').close();
        }
        break;
      case 'del-project':
        if (confirm('Xóa dự án và toàn bộ công việc thuộc dự án?')) {
          if (filters.project === String(id)) filters.project = '';
          act(() => api('DELETE', `/api/projects/${id}`), 'Đã xóa dự án');
        }
        break;
      case 'reset-pw': {
        const pw = prompt(`Mật khẩu mới cho ${userName(id)} (tối thiểu 6 ký tự):`);
        if (pw) act(() => api('PATCH', `/api/users/${id}`, { password: pw }), 'Đã đặt lại mật khẩu');
        break;
      }
      case 'deactivate':
        if (confirm(`Cho ${userName(id)} nghỉ? Tài khoản bị khóa, các việc chưa xong chuyển về "Chưa giao".`)) {
          act(() => api('DELETE', `/api/users/${id}`), 'Đã cho nghỉ');
        }
        break;
      case 'reactivate':
        act(() => api('PATCH', `/api/users/${id}`, { active: true }), 'Đã mở lại tài khoản');
        break;
      case 'edit-dept': {
        const d = dept(id);
        const name = prompt('Tên bộ phận:', d.name);
        if (name == null) break;
        const descr = prompt('Chức năng, nhiệm vụ:', d.descr);
        if (descr == null) break;
        act(() => api('PATCH', `/api/departments/${id}`, { name, descr }), 'Đã cập nhật bộ phận');
        break;
      }
      case 'del-dept':
        if (confirm('Xóa bộ phận này?')) act(() => api('DELETE', `/api/departments/${id}`), 'Đã xóa bộ phận');
        break;
      case 'filter-dept':
        Object.assign(filters, { project: '', assignee: '', q: '', dept: String(id) });
        break; // liên kết #board tự render qua hashchange
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
    const id = num(el.dataset.id);
    const v = el.value;
    switch (el.dataset.change) {
      case 'assignee':
        act(() => api('PATCH', `/api/tasks/${id}`, { assignee_id: num(v) }), v ? `Đã giao cho ${userName(num(v))}` : 'Đã bỏ giao việc');
        break;
      case 'status':
        act(() => api('PATCH', `/api/tasks/${id}`, { status: v }), 'Đã cập nhật trạng thái');
        break;
      case 'project-status':
        act(() => api('PATCH', `/api/projects/${id}`, { status: v }), 'Đã cập nhật dự án');
        break;
      case 'project-owner':
        act(() => api('PATCH', `/api/projects/${id}`, { owner_id: num(v) }), 'Đã đổi quản lý dự án');
        break;
      case 'user-dept':
        act(() => api('PATCH', `/api/users/${id}`, { dept_id: num(v) }), 'Đã chuyển bộ phận');
        break;
      case 'user-role':
        act(() => api('PATCH', `/api/users/${id}`, { role: v }), 'Đã đổi vai trò');
        break;
      case 'user-capacity':
        act(() => api('PATCH', `/api/users/${id}`, { capacity: Number(v) || 0 }));
        break;
      case 'dept-head':
        act(() => api('PATCH', `/api/departments/${id}`, { head_id: num(v) }), 'Đã bổ nhiệm trưởng bộ phận');
        break;
      default:
    }
  });

  document.addEventListener('input', (e) => {
    if (e.target.id === 'q') { filters.q = e.target.value; render(); }
  });

  document.addEventListener('submit', async (e) => {
    const form = e.target;
    const kind = form.dataset && form.dataset.form;
    if (!kind) return;
    e.preventDefault();
    const f = Object.fromEntries(new FormData(form));
    const id = num(form.dataset.id);
    const button = form.querySelector('button[type=submit]');
    if (button) button.disabled = true;
    try {
      switch (kind) {
        case 'login':
          await api('POST', '/api/login', f);
          if (!location.hash) history.replaceState(null, '', '#mine');
          await refresh();
          break;
        case 'setup':
          if (f.password !== f.password2) { toast('Hai mật khẩu không khớp', true); break; }
          await api('POST', '/api/setup', f);
          history.replaceState(null, '', '#mine');
          await refresh();
          toast('Đã tạo tài khoản. Xem dự án "Triển khai Projeck" để làm tiếp.');
          break;
        case 'password':
          if (f.new_password !== f.new_password2) { toast('Hai mật khẩu mới không khớp', true); break; }
          await api('POST', '/api/me/password', f);
          $('#dlg').close();
          toast('Đã đổi mật khẩu');
          break;
        case 'task':
          await act(() => api('POST', '/api/tasks', { ...f, project_id: num(f.project_id), assignee_id: num(f.assignee_id), estimate: Number(f.estimate) || 0 }),
            f.assignee_id ? `Đã giao việc cho ${userName(num(f.assignee_id))}` : 'Đã tạo công việc (chưa giao)');
          break;
        case 'task-edit': {
          const payload = { ...f };
          if ('project_id' in payload) payload.project_id = num(payload.project_id);
          if ('assignee_id' in payload) payload.assignee_id = num(payload.assignee_id);
          if ('estimate' in payload) payload.estimate = Number(payload.estimate) || 0;
          if (await act(() => api('PATCH', `/api/tasks/${id}`, payload), 'Đã lưu')) openTask(id);
          break;
        }
        case 'comment':
          if (await act(() => api('POST', `/api/tasks/${id}/comments`, f), 'Đã gửi bình luận')) openTask(id);
          break;
        case 'project':
          await act(() => api('POST', '/api/projects', { ...f, dept_id: num(f.dept_id), owner_id: num(f.owner_id) }), 'Đã tạo dự án');
          break;
        case 'user':
          await act(() => api('POST', '/api/users', { ...f, dept_id: num(f.dept_id), capacity: Number(f.capacity) || 0 }),
            `Đã tạo tài khoản ${f.username}. Gửi mật khẩu tạm cho nhân sự.`);
          break;
        case 'dept':
          await act(() => api('POST', '/api/departments', f), 'Đã thêm bộ phận');
          break;
        case 'company':
          await act(() => api('PATCH', '/api/settings', f), 'Đã lưu tên công ty');
          break;
        default:
      }
    } catch (err) {
      toast(err.message, true);
    } finally {
      if (button && button.isConnected) button.disabled = false;
    }
  });

  // Kéo thả thẻ giữa các cột trạng thái
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
    const t = task(num(e.dataTransfer.getData('text/plain')));
    if (t && t.status !== col.dataset.drop) {
      act(() => api('PATCH', `/api/tasks/${t.id}`, { status: col.dataset.drop }), 'Đã chuyển trạng thái');
    }
  });

  // Tự cập nhật khi đồng nghiệp thay đổi dữ liệu (20 giây/lần)
  setInterval(async () => {
    if (!S || document.hidden || $('#dlg').open) return;
    const a = document.activeElement;
    if (a && a.closest('#app') && /^(INPUT|TEXTAREA|SELECT)$/.test(a.tagName)) return;
    try {
      const fresh = await api('GET', '/api/state');
      const json = JSON.stringify(fresh);
      if (json !== lastJson) {
        if (fresh.unread > (S.unread || 0)) toast('Bạn có thông báo mới');
        S = fresh; me = fresh.me; lastJson = json;
        render();
      }
    } catch (e) { /* thử lại lần sau */ }
  }, 20000);

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') $('#notif').hidden = true;
  });
  window.addEventListener('hashchange', () => { $('#notif').hidden = true; render(); });

  (async function boot() {
    try {
      const b = await api('GET', '/api/bootstrap');
      setCompany(b.company);
      if (!b.me) { showLogin(b.needs_setup, b.company); return; }
      if (!location.hash) history.replaceState(null, '', '#mine');
      await refresh();
    } catch (e) {
      $('#app').innerHTML = `<section class="panel auth"><h2>Không kết nối được máy chủ</h2>
        <p>${esc(e.message)}</p><p class="muted">Hãy chạy <code>start_windows.bat</code> (hoặc <code>python server.py</code>)
        rồi mở đúng địa chỉ máy chủ in ra, ví dụ <code>http://localhost:8080</code>. Không mở trực tiếp file index.html.</p></section>`;
    }
  })();
})();
