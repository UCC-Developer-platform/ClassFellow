/// API endpoint constants corresponding to ClassFellow Mobile API Gateway v1.
class ApiEndpoints {
  // Authentication
  static const String authLogin = '/api/v1/auth/login/';

  // Teacher Workspace
  static const String teacherClasses = '/api/v1/teacher/classes/';
  static const String teacherRoster = '/api/v1/teacher/roster/';
  static const String teacherAttendanceSave = '/api/v1/teacher/attendance/save/';
  static const String teacherMarksSave = '/api/v1/teacher/marks/save/';

  // Parent Portal
  static const String parentChildren = '/api/v1/parent/children/';
  static const String parentFees = '/api/v1/parent/fees/';
  static const String parentAttendance = '/api/v1/parent/attendance/';
  static const String parentReportCard = '/api/v1/parent/report-card/';
}
