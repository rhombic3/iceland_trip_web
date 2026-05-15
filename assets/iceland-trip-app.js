const MODE_ICON = {
  car: '🚗',
  froad: '⛰️',
  walk: '🚶',
  boat: '🛥️',
  flight: '✈️',
  rest: '☕'
};

const ROUTE_COLOR = {
  car: 'var(--car)',
  froad: 'var(--froad)',
  walk: 'var(--walk)',
  boat: 'var(--boat)',
  flight: 'var(--flight)',
  rest: 'var(--rest)'
};

const HIGHLAND_OVERVIEW_FIRST_ROUTE = new Set(['d9', 'd10', 'd11', 'alt_laki']);
const HIGHLAND_NOTICE_DAYS = new Set(['d9', 'd10', 'd11', 'alt_mael', 'alt_thakgil', 'alt_laki']);

let currentDay = 'd1';
let currentRoute = null;

function byId(id) {
  return document.getElementById(id);
}

function textValue(value) {
  return value == null ? '' : String(value);
}

function escapeAttr(value) {
  return textValue(value)
    .replace(/&/g, '&amp;')
    .replace(/"/g, '&quot;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

function cleanRoutePoint(value) {
  return textValue(value).replace(/\s+/g, ' ').trim();
}

function isPopupSpot(id) {
  return Boolean(id && spots[id] && !id.startsWith('STAY_') && !['HELLA', 'MORA'].includes(id));
}

function splitWaypoint(value) {
  return textValue(value).split('|').map(cleanRoutePoint).filter(Boolean);
}

function expandWaypoints(values) {
  const points = [];

  (values || []).forEach(value => {
    splitWaypoint(value).forEach(point => points.push(point));
  });

  return points;
}

function uniqueOrdered(points) {
  const seen = new Set();
  const out = [];

  points.map(cleanRoutePoint).filter(Boolean).forEach(point => {
    const key = point.toLowerCase();

    if (!seen.has(key)) {
      seen.add(key);
      out.push(point);
    }
  });

  return out;
}

function googleEmbedSearch(query) {
  const params = new URLSearchParams({
    q: cleanRoutePoint(query) || 'Iceland',
    hl: 'zh-CN',
    output: 'embed'
  });

  return `https://maps.google.com/maps?${params.toString()}`;
}

function directionUrl(origin, destination, waypoints = [], mode = 'driving') {
  const params = new URLSearchParams();
  const stops = uniqueOrdered(waypoints).concat(cleanRoutePoint(destination)).filter(Boolean);

  params.set('f', 'd');
  params.set('saddr', cleanRoutePoint(origin));
  params.set('daddr', stops.join(' to: '));
  params.set('dirflg', mode === 'walking' ? 'w' : 'd');
  params.set('hl', 'zh-CN');
  params.set('output', 'embed');

  return `https://maps.google.com/maps?${params.toString()}`;
}

function googleEmbedRoute(route) {
  const waypoints = expandWaypoints(route.slice(5));
  return directionUrl(route[1], route[2], waypoints, route[3] || 'driving');
}

function googleEmbedOverview(day) {
  if (day === 'alt_westman') {
    return googleEmbedSearch('Vestmannaeyjar Iceland');
  }

  const dayData = days.find(item => item.id === day);
  const routes = (dayData && dayData.routes || []).filter(route => (route[3] || 'driving') === 'driving');

  if (!routes.length) {
    return googleEmbedSearch((dayData && dayData.title) || 'Iceland');
  }

  const first = routes[0];
  const last = routes[routes.length - 1];
  const isRoundTrip = cleanRoutePoint(first[1]).toLowerCase() === cleanRoutePoint(last[2]).toLowerCase();

  if (isRoundTrip || HIGHLAND_OVERVIEW_FIRST_ROUTE.has(day)) {
    return googleEmbedRoute(first);
  }

  const points = [];
  routes.forEach((route, index) => {
    expandWaypoints(route.slice(5)).forEach(point => points.push(point));

    if (index < routes.length - 1) {
      points.push(route[2]);
    }
  });

  return directionUrl(first[1], last[2], uniqueOrdered(points).slice(0, 9), 'driving');
}

function markerLabel(index) {
  return index < 9 ? String(index + 1) : String.fromCharCode(65 + index - 9);
}

function focusMapOnMobile() {
  if (!window.matchMedia || !window.matchMedia('(max-width: 860px)').matches) {
    return;
  }

  try {
    byId('mapPanel').scrollIntoView({ block: 'start', behavior: 'smooth' });
  } catch (error) {
    byId('mapPanel').scrollIntoView(true);
  }
}

function setDynamicMapSrc(src) {
  const frame = byId('mapFrame');

  frame.setAttribute('loading', 'eager');
  frame.style.display = 'block';
  frame.removeAttribute('srcdoc');

  if (frame.getAttribute('src') !== src) {
    frame.setAttribute('src', src);
  }
}

function embeddedPdf(kind) {
  const pdfs = typeof EMBEDDED_PDFS === 'undefined' ? {} : EMBEDDED_PDFS;
  return pdfs[kind] || null;
}

function openEmbeddedPdf(kind) {
  const item = embeddedPdf(kind);

  if (!item) {
    return;
  }

  try {
    const bin = atob(item.data);
    const bytes = new Uint8Array(bin.length);

    for (let i = 0; i < bin.length; i += 1) {
      bytes[i] = bin.charCodeAt(i);
    }

    const blob = new Blob([bytes], { type: 'application/pdf' });
    const url = URL.createObjectURL(blob);
    const opened = window.open(url, '_blank', 'noopener');

    if (!opened) {
      const link = document.createElement('a');
      link.href = url;
      link.download = item.filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
    }

    setTimeout(() => URL.revokeObjectURL(url), 120000);
  } catch (error) {
    alert('PDF 打开失败。请尝试使用最新版 Chrome/Edge，或允许浏览器打开新窗口。');
  }
}

function closeDrawer() {
  byId('drawer').classList.add('hidden');
}

function renderTabs() {
  byId('tabs').innerHTML = days
    .map(day => (
      `<button class="tab ${day.id === currentDay ? 'active' : ''}" onclick="selectDay('${escapeAttr(day.id)}')">` +
      `${day.tab}</button>`
    ))
    .join('');
}

function selectDay(day) {
  currentDay = day;
  renderTabs();
  renderDay(day);
  loadOverview(day);
}

function eventIsTransport(event) {
  return ['car', 'froad', 'flight'].includes(event[1]);
}

function routeIndexForEvent(dayData, event) {
  if (Array.isArray(event) && Number.isInteger(event[6])) {
    return event[6];
  }

  const spotId = Array.isArray(event) ? event[4] : event;

  if (!spotId || !spots[spotId]) {
    return dayData.routes.length ? 0 : null;
  }

  const spotNameKey = spots[spotId].name.split(' ')[0];
  const routeIndex = dayData.routes.findIndex(route => route.join(' ').includes(spotNameKey));

  return dayData.routes.length ? (routeIndex < 0 ? 0 : routeIndex) : null;
}

function imageSrc(src) {
  const value = String(src || '').trim();

  if (/^https:\/\/tse\.mm\.bing\.net\/th\?/i.test(value)) {
    const proxiedUrl = value.replace(/^https?:\/\//i, '');
    return `https://images.weserv.nl/?url=${encodeURIComponent(proxiedUrl)}&w=1200&h=760&fit=cover&output=jpg`;
  }

  return value;
}

function imgHTML(images) {
  const safe = [...new Set((images || []).filter(Boolean))].slice(0, 4);
  const content = safe
    .map(src => (
      `<img src="${escapeAttr(imageSrc(src))}" data-original-src="${escapeAttr(src)}" ` +
      'loading="eager" decoding="async" fetchpriority="high">'
    ))
    .join('');

  return `<div class="gallery" data-count="${Math.max(1, safe.length)}">${content}</div>`;
}

function spotThumbHTML(id) {
  const spot = spots[id] || {};
  const src = spot.imgs && spot.imgs[0];

  if (!src) {
    return '';
  }

  return `<img src="${escapeAttr(imageSrc(src))}" data-original-src="${escapeAttr(src)}" loading="eager" decoding="async">`;
}

function showSpot(id) {
  const spot = spots[id];

  if (!spot) {
    return;
  }

  byId('drawerGallery').innerHTML = imgHTML(spot.imgs);
  byId('drawerTitle').textContent = spot.name;
  byId('drawerText').textContent = spot.text;
  byId('drawerFee').textContent = `费用 / 注意：${spot.fee}`;

  const links = spot.links && spot.links.length ? spot.links : [['官网/参考', spot.url]].filter(link => link[1]);
  byId('drawerLinks').innerHTML = links.map(link => {
    if (String(link[1]).startsWith('pdf:')) {
      const kind = escapeAttr(String(link[1]).slice(4));
      if (!embeddedPdf(kind)) {
        return '';
      }

      return `<button type="button" onclick="openEmbeddedPdf('${kind}')">${link[0]} ↗</button>`;
    }

    return `<a href="${escapeAttr(link[1])}" target="_blank">${link[0]} ↗</a>`;
  }).join('');

  byId('drawer').classList.remove('hidden');
  focusMapOnMobile();
}

function renderDay(day) {
  const dayData = days.find(item => item.id === day);
  const stayHtml = dayData.stay ? `<span>住：${dayData.stay}</span>` : '';
  const popupIds = (dayData.spots || []).filter(isPopupSpot);
  const highlandNote = HIGHLAND_NOTICE_DAYS.has(day)
    ? '<div class="note">高地日/备选高地路线必须当天早上确认 Road.is、Vedur、SafeTravel；F-road 或涉水不稳时不要硬开，优先改普通道路或取消。</div>'
    : '';

  byId('content').innerHTML = [
    `<div class="dayTitle"><h2>${dayData.tab}<br>${dayData.title}</h2>${stayHtml}</div>`,
    highlandNote,
    '<div class="section">时间线 · 开车 / 游玩分开显示</div>',
    `<div class="timeline">${dayData.events.map((event, index) => eventHTML(day, event, index)).join('')}</div>`,
    popupIds.length ? spotGridHTML(popupIds) : ''
  ].join('');
}

function eventHTML(day, event, index) {
  const links = Array.isArray(event[5])
    ? `<div class="eventLinks">${event[5].map(link => (
      `<a href="${escapeAttr(link[1])}" target="_blank" onclick="event.stopPropagation()">${link[0]}</a>`
    )).join('')}</div>`
    : '';

  // const action = eventIsTransport(event)
  //   ? '点击只显示路线'
  //   : (isPopupSpot(event[4]) ? '点击只显示景点介绍' : '点击查看信息');
  const action = "";

  return (
    `<div class="event" onclick="onEvent('${escapeAttr(day)}',${index})">` +
      `<div class="time">${event[0]}</div>` +
      `<div class="mode ${event[1]}">${MODE_ICON[event[1]] || '•'}</div>` +
      `<div><strong>${event[2]}</strong><span>${event[3] || ''}</span><em>${action}</em>${links}</div>` +
    '</div>'
  );
}

function spotGridHTML(ids) {
  const cards = ids.map(id => {
    const spot = spots[id];

    return (
      `<div class="spot" onclick="showSpot('${escapeAttr(id)}')">` +
        `${spotThumbHTML(id)}` +
        `<div><b>${spot.name}</b><small>${spot.fee}</small></div>` +
      '</div>'
    );
  }).join('');

  return `<div class="section">景点图集</div><div class="spots">${cards}</div>`;
}

function onEvent(day, index) {
  const dayData = days.find(item => item.id === day);
  const event = dayData.events[index];

  if (eventIsTransport(event)) {
    const routeIdx = routeIndexForEvent(dayData, event);

    if (routeIdx !== null) {
      loadRoute(day, routeIdx);
    }
  } else {
    closeDrawer();
    renderSideSpots(day);

    if (isPopupSpot(event[4])) {
      showSpot(event[4]);
    }
  }

  document.querySelectorAll('.event').forEach((element, itemIndex) => {
    element.classList.toggle('active', itemIndex === index);
  });
}

function renderSideSpots(day) {
  const dayData = days.find(item => item.id === day);
  const ids = (dayData.spots || []).filter(isPopupSpot);
  const buttons = ids.map((id, index) => {
    const spot = spots[id];

    return (
      `<button class="spotBtn" onclick="showSpot('${escapeAttr(id)}')">` +
        `${spotThumbHTML(id)}` +
        `<div><b>${markerLabel(index)}. ${spot.name}</b><span>${spot.fee}</span></div>` +
      '</button>'
    );
  }).join('');

  byId('sidePanel').innerHTML = [
    '<h3>今日景点总览</h3>',
    '<div class="panelHint">右侧编号对应今日地点；点击景点可查看图片和注意事项。</div>',
    buttons
  ].join('');
}

function renderSideRoutes(day, active) {
  const dayData = days.find(item => item.id === day);
  const routeButtons = dayData.routes.map((route, index) => (
    `<button class="routeBtn ${index === active ? 'active' : ''}" onclick="loadRoute('${escapeAttr(day)}',${index})">` +
      `<i class="sw" style="background:${ROUTE_COLOR[route[4]] || '#999'}"></i>` +
      `<div><b>${route[0]}</b><span>${route[4] === 'froad' ? '高地/F-road' : route[3]}</span></div>` +
    '</button>'
  )).join('');

  byId('sidePanel').innerHTML = [
    '<h3>路线段</h3>',
    `<button class="btn light" style="width:100%;margin-bottom:9px" onclick="loadOverview('${escapeAttr(day)}')">返回景点总览</button>`,
    routeButtons
  ].join('');
}

function loadOverview(day) {
  const dayData = days.find(item => item.id === day);

  currentDay = day;
  currentRoute = null;
  closeDrawer();
  setDynamicMapSrc(googleEmbedOverview(day));

  byId('mapTitle').textContent = `${dayData.tab} · ${dayData.title} · 景点总览路线`;
  byId('mapSub').textContent = '默认显示当天动态 Google Maps 路线；往返高地日默认显示去程，返程可在路线段里切换。';

  renderSideSpots(day);
}

function loadRoute(day, index) {
  const dayData = days.find(item => item.id === day);
  const route = dayData.routes[index];

  if (!route) {
    loadOverview(day);
    return;
  }

  currentDay = day;
  currentRoute = index;
  closeDrawer();
  setDynamicMapSrc(googleEmbedRoute(route));

  byId('mapTitle').textContent = route[0];
  byId('mapSub').textContent = route[4] === 'froad'
    ? '高地路线只作规划参考，实际开放以 Road.is 为准。'
    : 'Google Maps 实际道路路线。';

  renderSideRoutes(day, index);
  focusMapOnMobile();
}

function reloadMap() {
  if (currentRoute === null) {
    loadOverview(currentDay);
  } else {
    loadRoute(currentDay, currentRoute);
  }
}

renderTabs();
renderDay(currentDay);
loadOverview(currentDay);
