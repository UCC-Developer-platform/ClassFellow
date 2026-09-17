/// Models supporting Teacher mobile workflows.

class ClassGroupInfo {
  final int id;
  final String name;
  final String section;
  final int? campusId;
  final String? campusName;

  const ClassGroupInfo({
    required this.id,
    required this.name,
    required this.section,
    this.campusId,
    this.campusName,
  });

  String get displayName => '$name - $section';

  factory ClassGroupInfo.fromJson(Map<String, dynamic> json) {
    return ClassGroupInfo(
      id: json['id'] as int? ?? 0,
      name: json['name'] as String? ?? '',
      section: json['section'] as String? ?? '',
      campusId: json['campus_id'] as int?,
      campusName: json['campus_name'] as String?,
    );
  }

  Map<String, dynamic> toJson() => {
        'id': id,
        'name': name,
        'section': section,
        'campus_id': campusId,
        'campus_name': campusName,
      };
}

class SubjectInfo {
  final int id;
  final String name;
  final String? code;

  const SubjectInfo({required this.id, required this.name, this.code});

  factory SubjectInfo.fromJson(Map<String, dynamic> json) {
    return SubjectInfo(
      id: json['id'] as int? ?? 0,
      name: json['name'] as String? ?? '',
      code: json['code'] as String?,
    );
  }

  Map<String, dynamic> toJson() => {
        'id': id,
        'name': name,
        'code': code,
      };
}

class SessionInfo {
  final int id;
  final String name;
  final bool isActive;

  const SessionInfo({required this.id, required this.name, required this.isActive});

  factory SessionInfo.fromJson(Map<String, dynamic> json) {
    return SessionInfo(
      id: json['id'] as int? ?? 0,
      name: json['name'] as String? ?? '',
      isActive: json['is_active'] as bool? ?? false,
    );
  }

  Map<String, dynamic> toJson() => {
        'id': id,
        'name': name,
        'is_active': isActive,
      };
}

class TeacherAllocation {
  final int allocationId;
  final ClassGroupInfo classGroup;
  final SubjectInfo subject;
  final SessionInfo academicSession;

  const TeacherAllocation({
    required this.allocationId,
    required this.classGroup,
    required this.subject,
    required this.academicSession,
  });

  factory TeacherAllocation.fromJson(Map<String, dynamic> json) {
    return TeacherAllocation(
      allocationId: json['allocation_id'] as int? ?? 0,
      classGroup: ClassGroupInfo.fromJson(json['class_group'] as Map<String, dynamic>? ?? {}),
      subject: SubjectInfo.fromJson(json['subject'] as Map<String, dynamic>? ?? {}),
      academicSession: SessionInfo.fromJson(json['academic_session'] as Map<String, dynamic>? ?? {}),
    );
  }

  Map<String, dynamic> toJson() => {
        'allocation_id': allocationId,
        'class_group': classGroup.toJson(),
        'subject': subject.toJson(),
        'academic_session': academicSession.toJson(),
      };
}

class RosterStudent {
  final int enrollmentId;
  final int studentId;
  final String rollNumber;
  final String admissionNumber;
  final String studentName;
  final String urduName;
  final String guardianName;
  final String guardianPhone;
  String status;
  String reasonNote;

  RosterStudent({
    required this.enrollmentId,
    required this.studentId,
    required this.rollNumber,
    required this.admissionNumber,
    required this.studentName,
    required this.urduName,
    required this.guardianName,
    required this.guardianPhone,
    required this.status,
    required this.reasonNote,
  });

  factory RosterStudent.fromJson(Map<String, dynamic> json) {
    return RosterStudent(
      enrollmentId: json['enrollment_id'] as int? ?? 0,
      studentId: json['student_id'] as int? ?? 0,
      rollNumber: json['roll_number'] as String? ?? '',
      admissionNumber: json['admission_number'] as String? ?? '',
      studentName: json['student_name'] as String? ?? '',
      urduName: json['urdu_name'] as String? ?? '',
      guardianName: json['guardian_name'] as String? ?? '',
      guardianPhone: json['guardian_phone'] as String? ?? '',
      status: json['status'] as String? ?? 'Present',
      reasonNote: json['reason_note'] as String? ?? '',
    );
  }

  Map<String, dynamic> toJson() => {
        'enrollment_id': enrollmentId,
        'student_id': studentId,
        'roll_number': rollNumber,
        'admission_number': admissionNumber,
        'student_name': studentName,
        'urdu_name': urduName,
        'guardian_name': guardianName,
        'guardian_phone': guardianPhone,
        'status': status,
        'reason_note': reasonNote,
      };
}

class RosterResponse {
  final int classGroupId;
  final String attendanceDate;
  final int totalStudents;
  final List<RosterStudent> roster;

  const RosterResponse({
    required this.classGroupId,
    required this.attendanceDate,
    required this.totalStudents,
    required this.roster,
  });

  factory RosterResponse.fromJson(Map<String, dynamic> json) {
    final list = json['roster'] as List<dynamic>? ?? [];
    return RosterResponse(
      classGroupId: json['class_group_id'] as int? ?? 0,
      attendanceDate: json['attendance_date'] as String? ?? '',
      totalStudents: json['total_students'] as int? ?? 0,
      roster: list.map((e) => RosterStudent.fromJson(e as Map<String, dynamic>)).toList(),
    );
  }
}
