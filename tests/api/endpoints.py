"""Endpoint yollari — OTOMATIK URETILDI, ELLE DUZENLEME.

Kaynak: contract/openapi.json (Postman koleksiyonundan turetildi).
Yenilemek icin:
    python contract/postman_to_openapi.py
    python contract/gen_endpoints.py

Parametreli yollar .format() ile kullanilir:
    api.get(endpoints.USERS_BY_USER_ID.format(userId=uid))
"""

# --- Admin: Audit History ----------------------------------------
ADMIN_HISTORY = "/v1/admin/history"  # GET

# --- Admin: Permission Groups ------------------------------------
ADMIN_PERMISSION_GROUPS = "/v1/admin/permission-groups"  # GET POST
ADMIN_PERMISSION_GROUPS_BY_PERM_GROUP_ID = "/v1/admin/permission-groups/{permGroupId}"  # DELETE GET PATCH
ADMIN_PERMISSION_GROUPS_PERMISSIONS_BY_PERM_GROUP_ID = "/v1/admin/permission-groups/{permGroupId}/permissions"  # POST
ADMIN_PERMISSION_GROUPS_PERMISSIONS_BY_PERM_GROUP_ID_PERMISSION_ID = "/v1/admin/permission-groups/{permGroupId}/permissions/{permissionId}"  # DELETE

# --- Admin: Permission Overrides ---------------------------------
ADMIN_USERS_PERMISSIONS_BY_USER_ID = "/v1/admin/users/{userId}/permissions"  # GET
ADMIN_USERS_PERMISSIONS_OVERRIDE_BY_USER_ID = "/v1/admin/users/{userId}/permissions/override"  # POST
ADMIN_USERS_PERMISSIONS_OVERRIDE_BY_USER_ID_PERMISSION_ID = "/v1/admin/users/{userId}/permissions/override/{permissionId}"  # DELETE

# --- Admin: Sensitive Fields -------------------------------------
ADMIN_SENSITIVE_FIELDS = "/v1/admin/sensitive-fields"  # GET POST
ADMIN_SENSITIVE_FIELDS_TEST_MASK = "/v1/admin/sensitive-fields/test-mask"  # POST
ADMIN_SENSITIVE_FIELDS_BY_SENSITIVE_FIELD_ID = "/v1/admin/sensitive-fields/{sensitiveFieldId}"  # DELETE GET PATCH

# --- Approvals ---------------------------------------------------
APPROVALS = "/v1/approvals"  # GET POST
APPROVALS_PENDING = "/v1/approvals/pending"  # GET
APPROVALS_BY_APPROVAL_ID = "/v1/approvals/{approvalId}"  # GET
APPROVALS_RESPOND_BY_APPROVAL_ID = "/v1/approvals/{approvalId}/respond"  # PATCH

# --- Auth --------------------------------------------------------
AUTH_LOGOUT = "/v1/auth/logout"  # POST
AUTH_ME = "/v1/auth/me"  # GET
AUTH_OTP_REQUEST = "/v1/auth/otp/request"  # POST
AUTH_OTP_RESEND = "/v1/auth/otp/resend"  # POST
AUTH_OTP_VERIFY = "/v1/auth/otp/verify"  # POST
AUTH_REFRESH = "/v1/auth/refresh"  # POST

# --- CMS Badges --------------------------------------------------
CMS_BADGES = "/v1/cms/badges"  # GET POST
CMS_BADGES_BY_CMS_BADGE_ID = "/v1/cms/badges/{cmsBadgeId}"  # DELETE GET PUT
CMS_SITES_BY_BADGE_SITE_ID = "/v1/cms/sites/{badgeSiteId}"  # DELETE
CMS_SITES_BADGES_BY_BADGE_SITE_ID = "/v1/cms/sites/{badgeSiteId}/badges"  # GET

# --- CMS Banners -------------------------------------------------
CMS_BADGES_BY_BANNER_BADGE_ID = "/v1/cms/badges/{bannerBadgeId}"  # DELETE
CMS_BANNERS = "/v1/cms/banners"  # GET POST
CMS_BANNERS_BY_CMS_BANNER_ID = "/v1/cms/banners/{cmsBannerId}"  # DELETE GET PUT
CMS_SITES_BY_BANNER_SITE_ID = "/v1/cms/sites/{bannerSiteId}"  # DELETE

# --- CMS Campuses ------------------------------------------------
CMS_SCHOOLS_99999999_9999_4999_8999_999999999999_CAMPUSES = "/v1/cms/schools/99999999-9999-4999-8999-999999999999/campuses"  # GET POST
CMS_SCHOOLS_BY_CMS_SCHOOL_BID = "/v1/cms/schools/{cmsSchoolBId}"  # DELETE
CMS_SCHOOLS_CAMPUSES_BY_CMS_SCHOOL_BID = "/v1/cms/schools/{cmsSchoolBId}/campuses"  # GET
CMS_SCHOOLS_CAMPUSES_99999999_9999_4999_8999_999999999999_BY_CMS_SCHOOL_BID = "/v1/cms/schools/{cmsSchoolBId}/campuses/99999999-9999-4999-8999-999999999999"  # DELETE GET
CMS_SCHOOLS_CAMPUSES_NOT_A_UUID_BY_CMS_SCHOOL_BID = "/v1/cms/schools/{cmsSchoolBId}/campuses/not-a-uuid"  # DELETE GET
CMS_SCHOOLS_CAMPUSES_BY_CMS_SCHOOL_BID_CMS_CAMPUS_ID = "/v1/cms/schools/{cmsSchoolBId}/campuses/{cmsCampusId}"  # DELETE GET PUT
CMS_SCHOOLS_CAMPUSES_BY_CMS_SCHOOL_ID = "/v1/cms/schools/{cmsSchoolId}/campuses"  # POST
CMS_SCHOOLS_CAMPUSES_99999999_9999_4999_8999_999999999999_BY_CMS_SCHOOL_ID = "/v1/cms/schools/{cmsSchoolId}/campuses/99999999-9999-4999-8999-999999999999"  # PUT
CMS_SCHOOLS_CAMPUSES_BY_CMS_SCHOOL_ID_CMS_CAMPUS_ID = "/v1/cms/schools/{cmsSchoolId}/campuses/{cmsCampusId}"  # DELETE GET PUT

# --- CMS Categories ----------------------------------------------
CMS_CATEGORIES = "/v1/cms/categories"  # GET POST
CMS_CATEGORIES_BY_CMS_CATEGORY_ID = "/v1/cms/categories/{cmsCategoryId}"  # DELETE GET PUT
CMS_SITES_BY_CATEGORY_SITE_ID = "/v1/cms/sites/{categorySiteId}"  # DELETE
CMS_SITES_CATEGORIES_BY_CATEGORY_SITE_ID = "/v1/cms/sites/{categorySiteId}/categories"  # GET

# --- CMS Events --------------------------------------------------
CMS_CATEGORIES_BY_EVENTS_CATEGORY_ID = "/v1/cms/categories/{eventsCategoryId}"  # DELETE
CMS_EVENTS = "/v1/cms/events"  # GET POST
CMS_EVENTS_BULK = "/v1/cms/events/bulk"  # DELETE
CMS_EVENTS_EXPORT = "/v1/cms/events/export"  # GET
CMS_EVENTS_BY_CMS_EVENT_ID = "/v1/cms/events/{cmsEventId}"  # DELETE GET PUT
CMS_EVENTS_PRICE_GROUPS_BY_CMS_EVENT_ID = "/v1/cms/events/{cmsEventId}/price-groups"  # POST
CMS_EVENTS_PRICE_GROUPS_BY_CMS_EVENT_ID_CMS_PRICE_GROUP_BUS_ID = "/v1/cms/events/{cmsEventId}/price-groups/{cmsPriceGroupBusId}"  # DELETE
CMS_EVENTS_PRICE_GROUPS_BY_CMS_EVENT_ID_CMS_PRICE_GROUP_ID = "/v1/cms/events/{cmsEventId}/price-groups/{cmsPriceGroupId}"  # PUT
CMS_PROJECTS = "/v1/cms/projects"  # GET
CMS_SCHOOLS = "/v1/cms/schools"  # GET POST
CMS_SCHOOLS_CAMPUSES_BY_PRICE_GROUP_SCHOOL_ID = "/v1/cms/schools/{priceGroupSchoolId}/campuses"  # POST
CMS_SCHOOLS_CAMPUSES_BY_PRICE_GROUP_SCHOOL_ID_PRICE_GROUP_CAMPUS_ID = "/v1/cms/schools/{priceGroupSchoolId}/campuses/{priceGroupCampusId}"  # DELETE

# --- CMS Schools -------------------------------------------------
CMS_SCHOOLS_99999999_9999_4999_8999_999999999999 = "/v1/cms/schools/99999999-9999-4999-8999-999999999999"  # DELETE GET PUT
CMS_SCHOOLS_NOT_A_UUID = "/v1/cms/schools/not-a-uuid"  # DELETE
CMS_SCHOOLS_BY_CMS_SCHOOL_DEL_ID = "/v1/cms/schools/{cmsSchoolDelId}"  # DELETE GET
CMS_SCHOOLS_BY_CMS_SCHOOL_ID = "/v1/cms/schools/{cmsSchoolId}"  # DELETE GET PUT

# --- CMS Sites ---------------------------------------------------
CMS_PUBLIC_SITES = "/v1/cms/public/sites"  # GET
CMS_SITES = "/v1/cms/sites"  # GET POST
CMS_SITES_BY_CMS_SITE_ID = "/v1/cms/sites/{cmsSiteId}"  # DELETE GET PUT

# --- Calendar ----------------------------------------------------
CALENDAR_EVENTS = "/v1/calendar/events"  # GET

# --- Customers ---------------------------------------------------
CUSTOMERS = "/v1/customers"  # GET POST
CUSTOMERS_SUMMARY = "/v1/customers/summary"  # GET
CUSTOMERS_BY_CUSTOMER_ID = "/v1/customers/{customerId}"  # DELETE GET PATCH
CUSTOMERS_CONTACTS_BY_CUSTOMER_ID = "/v1/customers/{customerId}/contacts"  # GET POST
CUSTOMERS_CONTACTS_BY_CUSTOMER_ID_CONTACT_ID = "/v1/customers/{customerId}/contacts/{contactId}"  # DELETE PATCH
CUSTOMERS_NOTES_BY_CUSTOMER_ID = "/v1/customers/{customerId}/notes"  # GET POST
CUSTOMERS_NOTES_BY_CUSTOMER_ID_NOTE_ID = "/v1/customers/{customerId}/notes/{noteId}"  # DELETE GET PATCH
CUSTOMERS_PREFERENCES_BY_CUSTOMER_ID = "/v1/customers/{customerId}/preferences"  # GET POST
CUSTOMERS_PREFERENCES_BY_CUSTOMER_ID_PREF_ID = "/v1/customers/{customerId}/preferences/{prefId}"  # DELETE PATCH
CUSTOMERS_REPORT_BY_CUSTOMER_ID = "/v1/customers/{customerId}/report"  # GET

# --- Departments -------------------------------------------------
DEPARTMENTS = "/v1/departments"  # GET POST
DEPARTMENTS_BY_DEPARTMENT_ID = "/v1/departments/{departmentId}"  # DELETE PATCH

# --- Error Response Examples -------------------------------------
CUSTOMERS_00000000_0000_0000_0000_000000000000 = "/v1/customers/00000000-0000-0000-0000-000000000000"  # GET

# --- Expenses ----------------------------------------------------
EXPENSES = "/v1/expenses"  # GET POST
EXPENSES_SCAN = "/v1/expenses/scan"  # POST
EXPENSES_SCAN_BY_SCAN_ID = "/v1/expenses/scan/{scanId}"  # GET
EXPENSES_BY_EXPENSE_ID = "/v1/expenses/{expenseId}"  # GET PATCH
EXPENSES_APPROVE_BY_EXPENSE_ID = "/v1/expenses/{expenseId}/approve"  # PATCH

# --- Files -------------------------------------------------------
FILES = "/v1/files"  # GET
FILES_00000000_0000_0000_0000_0000000000FF_PREVIEW = "/v1/files/00000000-0000-0000-0000-0000000000ff/preview"  # GET
FILES_UPLOAD = "/v1/files/upload"  # POST
FILES_BY_FILE_ID = "/v1/files/{fileId}"  # DELETE GET
FILES_DOWNLOAD_BY_FILE_ID = "/v1/files/{fileId}/download"  # GET
FILES_PREVIEW_BY_FILE_ID = "/v1/files/{fileId}/preview"  # GET

# --- Locations ---------------------------------------------------
LOCATIONS_PROVINCES = "/v1/locations/provinces"  # GET
LOCATIONS_PROVINCES_34_DISTRICTS = "/v1/locations/provinces/34/districts"  # GET

# --- Lookups -----------------------------------------------------
LOOKUPS_DEPARTMENTS = "/v1/lookups/departments"  # GET
LOOKUPS_ENUMS = "/v1/lookups/enums"  # GET
LOOKUPS_ENUMS_CUSTOMER_KIND = "/v1/lookups/enums/customerKind"  # GET
LOOKUPS_ENUMS_PROGRAM_TYPE = "/v1/lookups/enums/programType"  # GET
LOOKUPS_ENUMS_QUOTE_CANCELLATION_REASON = "/v1/lookups/enums/quoteCancellationReason"  # GET
LOOKUPS_ENUMS_REQUEST_PRIORITY = "/v1/lookups/enums/requestPriority"  # GET
LOOKUPS_ROLES = "/v1/lookups/roles"  # GET
LOOKUPS_USERS = "/v1/lookups/users"  # GET

# --- Notifications -----------------------------------------------
NOTIFICATIONS = "/v1/notifications"  # GET
NOTIFICATIONS_READ_ALL = "/v1/notifications/read-all"  # POST
NOTIFICATIONS_READ_BULK = "/v1/notifications/read-bulk"  # POST
NOTIFICATIONS_READ_BY_NOTIFICATION_ID = "/v1/notifications/{notificationId}/read"  # PATCH

# --- Participants ------------------------------------------------
PROJECTS_PARTICIPANTS_TEMPLATE = "/v1/projects/participants/template"  # GET
PROJECTS_PARTICIPANTS_BY_PROJECT_ID = "/v1/projects/{projectId}/participants"  # GET POST
PROJECTS_PARTICIPANTS_IMPORT_BY_PROJECT_ID = "/v1/projects/{projectId}/participants/import"  # POST
PROJECTS_PARTICIPANTS_BY_PROJECT_ID_PARTICIPANT_ID = "/v1/projects/{projectId}/participants/{participantId}"  # DELETE PATCH

# --- Places ------------------------------------------------------
PLACES_AUTOCOMPLETE = "/v1/places/autocomplete"  # GET
PLACES_DETAILS = "/v1/places/details"  # GET

# --- Project Notes -----------------------------------------------
PROJECTS_NOTES_BY_PROJECT_ID = "/v1/projects/{projectId}/notes"  # GET POST
PROJECTS_NOTES_BY_PROJECT_ID_NOTE_ID = "/v1/projects/{projectId}/notes/{noteId}"  # DELETE PATCH

# --- Projects ----------------------------------------------------
PROJECTS = "/v1/projects"  # GET POST
PROJECTS_DRAFTS = "/v1/projects/drafts"  # GET POST
PROJECTS_DRAFTS_BY_TP379_DRAFT_ID = "/v1/projects/drafts/{tp379DraftId}"  # GET
PROJECTS_DRAFTS_BY_TP379_REQ_DRAFT_ID = "/v1/projects/drafts/{tp379ReqDraftId}"  # GET
PROJECTS_EXPORT = "/v1/projects/export"  # GET
PROJECTS_BY_PROJECT_ID = "/v1/projects/{projectId}"  # GET PATCH
PROJECTS_PARTICIPANTS_EXPORT_BY_PROJECT_ID = "/v1/projects/{projectId}/participants/export"  # GET
PROJECTS_REQUESTS_BY_PROJECT_ID = "/v1/projects/{projectId}/requests"  # POST
PROJECTS_STATUS_BY_PROJECT_ID = "/v1/projects/{projectId}/status"  # PATCH
PROJECTS_BY_TP310_BARE_PROJECT_ID = "/v1/projects/{tp310BareProjectId}"  # GET
PROJECTS_BY_TP310_VIP_PROJECT_ID = "/v1/projects/{tp310VipProjectId}"  # GET

# --- Quotes ------------------------------------------------------
QUOTES = "/v1/quotes"  # GET POST
QUOTES_BY_QUOTE_ID = "/v1/quotes/{quoteId}"  # GET PATCH
QUOTES_APPROVE_BY_QUOTE_ID = "/v1/quotes/{quoteId}/approve"  # POST
QUOTES_APPROVE_INTERNAL_BY_QUOTE_ID = "/v1/quotes/{quoteId}/approve-internal"  # POST
QUOTES_CANCEL_BY_QUOTE_ID = "/v1/quotes/{quoteId}/cancel"  # POST
QUOTES_REGENERATE_PDF_BY_QUOTE_ID = "/v1/quotes/{quoteId}/regenerate-pdf"  # POST
QUOTES_REJECT_BY_QUOTE_ID = "/v1/quotes/{quoteId}/reject"  # POST
QUOTES_RETURN_TO_DRAFT_BY_QUOTE_ID = "/v1/quotes/{quoteId}/return-to-draft"  # POST
QUOTES_REVISION_REQUEST_BY_QUOTE_ID = "/v1/quotes/{quoteId}/revision-request"  # POST
QUOTES_SEND_BY_QUOTE_ID = "/v1/quotes/{quoteId}/send"  # POST
QUOTES_SUBMIT_INTERNAL_BY_QUOTE_ID = "/v1/quotes/{quoteId}/submit-internal"  # POST

# --- Requests ----------------------------------------------------
REQUESTS = "/v1/requests"  # GET POST
REQUESTS_DRAFTS = "/v1/requests/drafts"  # POST
REQUESTS_DRAFTS_BY_REQUEST_DRAFT_ID = "/v1/requests/drafts/{requestDraftId}"  # DELETE GET PATCH
REQUESTS_PENDING_PROJECT = "/v1/requests/pending-project"  # GET
REQUESTS_BY_REQUEST_ID = "/v1/requests/{requestId}"  # GET PATCH
REQUESTS_ACTIVITIES_BY_REQUEST_ID = "/v1/requests/{requestId}/activities"  # GET
REQUESTS_FILES_BY_REQUEST_ID = "/v1/requests/{requestId}/files"  # GET POST
REQUESTS_FILES_BY_REQUEST_ID_REQUEST_FILE_ID = "/v1/requests/{requestId}/files/{requestFileId}"  # DELETE
REQUESTS_SERVICES_BY_REQUEST_ID = "/v1/requests/{requestId}/services"  # POST

# --- Roles -------------------------------------------------------
ROLES = "/v1/roles"  # GET POST
ROLES_PERMISSIONS = "/v1/roles/permissions"  # GET
ROLES_BY_ROLE_ID = "/v1/roles/{roleId}"  # DELETE GET PATCH

# --- Sidebar -----------------------------------------------------
SIDEBAR_MENU = "/v1/sidebar/menu"  # GET

# --- Tasks -------------------------------------------------------
TASKS = "/v1/tasks"  # GET POST
TASKS_SUMMARY = "/v1/tasks/summary"  # GET
TASKS_BY_TASK_ID = "/v1/tasks/{taskId}"  # GET PATCH
TASKS_ACTIVITIES_BY_TASK_ID = "/v1/tasks/{taskId}/activities"  # GET
TASKS_ALTERNATIVES_BY_TASK_ID = "/v1/tasks/{taskId}/alternatives"  # GET POST
TASKS_ALTERNATIVES_BY_TASK_ID_TASK_ALT_ID = "/v1/tasks/{taskId}/alternatives/{taskAltId}"  # DELETE PATCH
TASKS_ALTERNATIVES_SELECT_BY_TASK_ID_TASK_ALT_ID = "/v1/tasks/{taskId}/alternatives/{taskAltId}/select"  # PATCH
TASKS_COMMENTS_BY_TASK_ID = "/v1/tasks/{taskId}/comments"  # POST
TASKS_FILES_BY_TASK_ID = "/v1/tasks/{taskId}/files"  # GET POST
TASKS_FILES_BY_TASK_ID_TASK_FILE_ID = "/v1/tasks/{taskId}/files/{taskFileId}"  # DELETE
TASKS_FILES_DOWNLOAD_BY_TASK_ID_TASK_FILE_ID = "/v1/tasks/{taskId}/files/{taskFileId}/download"  # GET
TASKS_FILES_PREVIEW_BY_TASK_ID_TASK_FILE_ID = "/v1/tasks/{taskId}/files/{taskFileId}/preview"  # GET
TASKS_PRICES_BY_TASK_ID = "/v1/tasks/{taskId}/prices"  # POST
TASKS_PRICES_BY_TASK_ID_TASK_PRICE_ID = "/v1/tasks/{taskId}/prices/{taskPriceId}"  # DELETE PATCH
TASKS_PRICES_SELECT_BY_TASK_ID_TASK_PRICE_ID = "/v1/tasks/{taskId}/prices/{taskPriceId}/select"  # PATCH

# --- Users -------------------------------------------------------
USERS = "/v1/users"  # GET POST
USERS_BY_USER_ID = "/v1/users/{userId}"  # DELETE GET PATCH

# --- default -----------------------------------------------------
HEALTH = "/health"  # GET

# Tum yollar — kapsam/smoke testleri icin
ALL_PATHS = (
    ADMIN_HISTORY,
    ADMIN_PERMISSION_GROUPS,
    ADMIN_PERMISSION_GROUPS_BY_PERM_GROUP_ID,
    ADMIN_PERMISSION_GROUPS_PERMISSIONS_BY_PERM_GROUP_ID,
    ADMIN_PERMISSION_GROUPS_PERMISSIONS_BY_PERM_GROUP_ID_PERMISSION_ID,
    ADMIN_USERS_PERMISSIONS_BY_USER_ID,
    ADMIN_USERS_PERMISSIONS_OVERRIDE_BY_USER_ID,
    ADMIN_USERS_PERMISSIONS_OVERRIDE_BY_USER_ID_PERMISSION_ID,
    ADMIN_SENSITIVE_FIELDS,
    ADMIN_SENSITIVE_FIELDS_TEST_MASK,
    ADMIN_SENSITIVE_FIELDS_BY_SENSITIVE_FIELD_ID,
    APPROVALS,
    APPROVALS_PENDING,
    APPROVALS_BY_APPROVAL_ID,
    APPROVALS_RESPOND_BY_APPROVAL_ID,
    AUTH_LOGOUT,
    AUTH_ME,
    AUTH_OTP_REQUEST,
    AUTH_OTP_RESEND,
    AUTH_OTP_VERIFY,
    AUTH_REFRESH,
    CMS_BADGES,
    CMS_BADGES_BY_CMS_BADGE_ID,
    CMS_SITES_BY_BADGE_SITE_ID,
    CMS_SITES_BADGES_BY_BADGE_SITE_ID,
    CMS_BADGES_BY_BANNER_BADGE_ID,
    CMS_BANNERS,
    CMS_BANNERS_BY_CMS_BANNER_ID,
    CMS_SITES_BY_BANNER_SITE_ID,
    CMS_SCHOOLS_99999999_9999_4999_8999_999999999999_CAMPUSES,
    CMS_SCHOOLS_BY_CMS_SCHOOL_BID,
    CMS_SCHOOLS_CAMPUSES_BY_CMS_SCHOOL_BID,
    CMS_SCHOOLS_CAMPUSES_99999999_9999_4999_8999_999999999999_BY_CMS_SCHOOL_BID,
    CMS_SCHOOLS_CAMPUSES_NOT_A_UUID_BY_CMS_SCHOOL_BID,
    CMS_SCHOOLS_CAMPUSES_BY_CMS_SCHOOL_BID_CMS_CAMPUS_ID,
    CMS_SCHOOLS_CAMPUSES_BY_CMS_SCHOOL_ID,
    CMS_SCHOOLS_CAMPUSES_99999999_9999_4999_8999_999999999999_BY_CMS_SCHOOL_ID,
    CMS_SCHOOLS_CAMPUSES_BY_CMS_SCHOOL_ID_CMS_CAMPUS_ID,
    CMS_CATEGORIES,
    CMS_CATEGORIES_BY_CMS_CATEGORY_ID,
    CMS_SITES_BY_CATEGORY_SITE_ID,
    CMS_SITES_CATEGORIES_BY_CATEGORY_SITE_ID,
    CMS_CATEGORIES_BY_EVENTS_CATEGORY_ID,
    CMS_EVENTS,
    CMS_EVENTS_BULK,
    CMS_EVENTS_EXPORT,
    CMS_EVENTS_BY_CMS_EVENT_ID,
    CMS_EVENTS_PRICE_GROUPS_BY_CMS_EVENT_ID,
    CMS_EVENTS_PRICE_GROUPS_BY_CMS_EVENT_ID_CMS_PRICE_GROUP_BUS_ID,
    CMS_EVENTS_PRICE_GROUPS_BY_CMS_EVENT_ID_CMS_PRICE_GROUP_ID,
    CMS_PROJECTS,
    CMS_SCHOOLS,
    CMS_SCHOOLS_CAMPUSES_BY_PRICE_GROUP_SCHOOL_ID,
    CMS_SCHOOLS_CAMPUSES_BY_PRICE_GROUP_SCHOOL_ID_PRICE_GROUP_CAMPUS_ID,
    CMS_SCHOOLS_99999999_9999_4999_8999_999999999999,
    CMS_SCHOOLS_NOT_A_UUID,
    CMS_SCHOOLS_BY_CMS_SCHOOL_DEL_ID,
    CMS_SCHOOLS_BY_CMS_SCHOOL_ID,
    CMS_PUBLIC_SITES,
    CMS_SITES,
    CMS_SITES_BY_CMS_SITE_ID,
    CALENDAR_EVENTS,
    CUSTOMERS,
    CUSTOMERS_SUMMARY,
    CUSTOMERS_BY_CUSTOMER_ID,
    CUSTOMERS_CONTACTS_BY_CUSTOMER_ID,
    CUSTOMERS_CONTACTS_BY_CUSTOMER_ID_CONTACT_ID,
    CUSTOMERS_NOTES_BY_CUSTOMER_ID,
    CUSTOMERS_NOTES_BY_CUSTOMER_ID_NOTE_ID,
    CUSTOMERS_PREFERENCES_BY_CUSTOMER_ID,
    CUSTOMERS_PREFERENCES_BY_CUSTOMER_ID_PREF_ID,
    CUSTOMERS_REPORT_BY_CUSTOMER_ID,
    DEPARTMENTS,
    DEPARTMENTS_BY_DEPARTMENT_ID,
    CUSTOMERS_00000000_0000_0000_0000_000000000000,
    EXPENSES,
    EXPENSES_SCAN,
    EXPENSES_SCAN_BY_SCAN_ID,
    EXPENSES_BY_EXPENSE_ID,
    EXPENSES_APPROVE_BY_EXPENSE_ID,
    FILES,
    FILES_00000000_0000_0000_0000_0000000000FF_PREVIEW,
    FILES_UPLOAD,
    FILES_BY_FILE_ID,
    FILES_DOWNLOAD_BY_FILE_ID,
    FILES_PREVIEW_BY_FILE_ID,
    LOCATIONS_PROVINCES,
    LOCATIONS_PROVINCES_34_DISTRICTS,
    LOOKUPS_DEPARTMENTS,
    LOOKUPS_ENUMS,
    LOOKUPS_ENUMS_CUSTOMER_KIND,
    LOOKUPS_ENUMS_PROGRAM_TYPE,
    LOOKUPS_ENUMS_QUOTE_CANCELLATION_REASON,
    LOOKUPS_ENUMS_REQUEST_PRIORITY,
    LOOKUPS_ROLES,
    LOOKUPS_USERS,
    NOTIFICATIONS,
    NOTIFICATIONS_READ_ALL,
    NOTIFICATIONS_READ_BULK,
    NOTIFICATIONS_READ_BY_NOTIFICATION_ID,
    PROJECTS_PARTICIPANTS_TEMPLATE,
    PROJECTS_PARTICIPANTS_BY_PROJECT_ID,
    PROJECTS_PARTICIPANTS_IMPORT_BY_PROJECT_ID,
    PROJECTS_PARTICIPANTS_BY_PROJECT_ID_PARTICIPANT_ID,
    PLACES_AUTOCOMPLETE,
    PLACES_DETAILS,
    PROJECTS_NOTES_BY_PROJECT_ID,
    PROJECTS_NOTES_BY_PROJECT_ID_NOTE_ID,
    PROJECTS,
    PROJECTS_DRAFTS,
    PROJECTS_DRAFTS_BY_TP379_DRAFT_ID,
    PROJECTS_DRAFTS_BY_TP379_REQ_DRAFT_ID,
    PROJECTS_EXPORT,
    PROJECTS_BY_PROJECT_ID,
    PROJECTS_PARTICIPANTS_EXPORT_BY_PROJECT_ID,
    PROJECTS_REQUESTS_BY_PROJECT_ID,
    PROJECTS_STATUS_BY_PROJECT_ID,
    PROJECTS_BY_TP310_BARE_PROJECT_ID,
    PROJECTS_BY_TP310_VIP_PROJECT_ID,
    QUOTES,
    QUOTES_BY_QUOTE_ID,
    QUOTES_APPROVE_BY_QUOTE_ID,
    QUOTES_APPROVE_INTERNAL_BY_QUOTE_ID,
    QUOTES_CANCEL_BY_QUOTE_ID,
    QUOTES_REGENERATE_PDF_BY_QUOTE_ID,
    QUOTES_REJECT_BY_QUOTE_ID,
    QUOTES_RETURN_TO_DRAFT_BY_QUOTE_ID,
    QUOTES_REVISION_REQUEST_BY_QUOTE_ID,
    QUOTES_SEND_BY_QUOTE_ID,
    QUOTES_SUBMIT_INTERNAL_BY_QUOTE_ID,
    REQUESTS,
    REQUESTS_DRAFTS,
    REQUESTS_DRAFTS_BY_REQUEST_DRAFT_ID,
    REQUESTS_PENDING_PROJECT,
    REQUESTS_BY_REQUEST_ID,
    REQUESTS_ACTIVITIES_BY_REQUEST_ID,
    REQUESTS_FILES_BY_REQUEST_ID,
    REQUESTS_FILES_BY_REQUEST_ID_REQUEST_FILE_ID,
    REQUESTS_SERVICES_BY_REQUEST_ID,
    ROLES,
    ROLES_PERMISSIONS,
    ROLES_BY_ROLE_ID,
    SIDEBAR_MENU,
    TASKS,
    TASKS_SUMMARY,
    TASKS_BY_TASK_ID,
    TASKS_ACTIVITIES_BY_TASK_ID,
    TASKS_ALTERNATIVES_BY_TASK_ID,
    TASKS_ALTERNATIVES_BY_TASK_ID_TASK_ALT_ID,
    TASKS_ALTERNATIVES_SELECT_BY_TASK_ID_TASK_ALT_ID,
    TASKS_COMMENTS_BY_TASK_ID,
    TASKS_FILES_BY_TASK_ID,
    TASKS_FILES_BY_TASK_ID_TASK_FILE_ID,
    TASKS_FILES_DOWNLOAD_BY_TASK_ID_TASK_FILE_ID,
    TASKS_FILES_PREVIEW_BY_TASK_ID_TASK_FILE_ID,
    TASKS_PRICES_BY_TASK_ID,
    TASKS_PRICES_BY_TASK_ID_TASK_PRICE_ID,
    TASKS_PRICES_SELECT_BY_TASK_ID_TASK_PRICE_ID,
    USERS,
    USERS_BY_USER_ID,
    HEALTH,
)
