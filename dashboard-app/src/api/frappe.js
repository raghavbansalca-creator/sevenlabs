/**
 * Frappe REST API client
 * Uses session cookie (same-origin) + CSRF token for auth
 */

function getCsrfToken() {
  // Set by the Frappe Web Page template
  if (window.csrf_token) return window.csrf_token
  // Fallback: read from cookie
  const match = document.cookie.match(/csrf_token=([^;]+)/)
  if (match) return decodeURIComponent(match[1])
  // Frappe requires the header to exist; 'none' works for same-origin
  return 'none'
}

async function request(url, options = {}) {
  const headers = {
    'Accept': 'application/json',
    'X-Frappe-CSRF-Token': getCsrfToken(),
    ...options.headers,
  }

  if (options.body && !(options.body instanceof FormData)) {
    headers['Content-Type'] = 'application/json'
  }

  const res = await fetch(url, {
    credentials: 'same-origin',
    ...options,
    headers,
  })

  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(`API Error ${res.status}: ${text}`)
  }

  const data = await res.json()
  return data
}

/**
 * Call a Frappe whitelisted method
 */
export async function call(method, args = {}) {
  const data = await request(`/api/method/${method}`, {
    method: 'POST',
    body: JSON.stringify(args),
  })
  return data.message
}

/**
 * Get a list of documents
 * Uses frappe.client.get_list (POST) to support or_filters
 */
export async function getList(doctype, {
  fields = ['name'],
  filters = [],
  orFilters,
  orderBy = 'modified desc',
  limit = 20,
  limitStart = 0,
} = {}) {
  const args = {
    doctype,
    fields,
    filters,
    order_by: orderBy,
    limit_page_length: limit,
    limit_start: limitStart,
  }
  if (orFilters) {
    args.or_filters = orFilters
  }
  return call('frappe.client.get_list', args)
}

/**
 * Get a single document
 */
export async function getDoc(doctype, name) {
  const data = await request(`/api/resource/${doctype}/${encodeURIComponent(name)}`)
  return data.data
}

/**
 * Set a single field value
 */
export async function setValue(doctype, name, fieldname, value) {
  const data = await request(`/api/resource/${doctype}/${encodeURIComponent(name)}`, {
    method: 'PUT',
    body: JSON.stringify({ [fieldname]: value }),
  })
  return data.data
}

/**
 * Create a new document
 */
export async function insertDoc(doc) {
  const data = await request(`/api/resource/${doc.doctype}`, {
    method: 'POST',
    body: JSON.stringify(doc),
  })
  return data.data
}

/**
 * Upload a file
 */
export async function uploadFile(file, doctype, docname) {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('doctype', doctype)
  formData.append('docname', docname)
  formData.append('is_private', '0')

  const data = await request('/api/method/upload_file', {
    method: 'POST',
    body: formData,
  })
  return data.message
}

/**
 * Add assignment
 */
export async function addAssignment(doctype, name, userEmail) {
  return call('frappe.desk.form.assign_to.add', {
    doctype,
    name,
    assign_to: [userEmail],
  })
}

/**
 * Remove assignment
 */
export async function removeAssignment(doctype, name, userEmail) {
  return call('frappe.desk.form.assign_to.remove', {
    doctype,
    name,
    assign_to: userEmail,
  })
}

/**
 * Get logged in user info
 */
export async function getLoggedUser() {
  return call('frappe.auth.get_logged_user')
}
