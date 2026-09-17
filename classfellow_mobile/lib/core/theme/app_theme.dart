import 'package:flutter/material.dart';

/// ClassFellow Mobile Design Tokens & Theme System.
/// Adheres strictly to the Slate-900 & Emerald aesthetic tokens.
class AppTheme {
  // Color Palette
  static const Color slate900 = Color(0xFF0F172A); // Background
  static const Color slate800 = Color(0xFF1E293B); // Surface / Cards
  static const Color slate700 = Color(0xFF334155); // Borders & Dividers
  static const Color slate600 = Color(0xFF475569); // Muted Elements
  static const Color emerald500 = Color(0xFF10B981); // Primary Accent
  static const Color emerald600 = Color(0xFF059669); // Active / Hover
  static const Color amber500 = Color(0xFFF59E0B); // Warnings / Late
  static const Color rose500 = Color(0xFFEF4444); // Errors / Absent
  static const Color slate50 = Color(0xFFF8FAFC); // Text Primary
  static const Color slate400 = Color(0xFF94A3B8); // Text Secondary

  static ThemeData get darkTheme {
    return ThemeData(
      brightness: Brightness.dark,
      scaffoldBackgroundColor: slate900,
      primaryColor: emerald500,
      colorScheme: const ColorScheme.dark(
        primary: emerald500,
        secondary: emerald600,
        surface: slate800,
        error: rose500,
        onPrimary: slate50,
        onSecondary: slate50,
        onSurface: slate50,
        onError: slate50,
      ),
      appBarTheme: const AppBarTheme(
        backgroundColor: slate900,
        elevation: 0,
        centerTitle: false,
        titleTextStyle: TextStyle(
          color: slate50,
          fontSize: 20,
          fontWeight: FontWeight.w700,
          letterSpacing: -0.5,
        ),
        iconTheme: IconThemeData(color: slate50),
      ),
      cardTheme: CardTheme(
        color: slate800,
        elevation: 2,
        margin: const EdgeInsets.symmetric(vertical: 6, horizontal: 0),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(12),
          side: const BorderSide(color: slate700, width: 1),
        ),
      ),
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: emerald500,
          foregroundColor: slate50,
          padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 14),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(10),
          ),
          textStyle: const TextStyle(
            fontSize: 15,
            fontWeight: FontWeight.w600,
            letterSpacing: 0.2,
          ),
          elevation: 0,
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          foregroundColor: emerald500,
          side: const BorderSide(color: emerald500, width: 1.5),
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(10),
          ),
        ),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: slate800,
        contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
        hintStyle: const TextStyle(color: slate400, fontSize: 14),
        labelStyle: const TextStyle(color: slate400, fontSize: 14),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(10),
          borderSide: const BorderSide(color: slate700, width: 1),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(10),
          borderSide: const BorderSide(color: slate700, width: 1),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(10),
          borderSide: const BorderSide(color: emerald500, width: 1.8),
        ),
        errorBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(10),
          borderSide: const BorderSide(color: rose500, width: 1.5),
        ),
      ),
      tabBarTheme: const TabBarTheme(
        labelColor: emerald500,
        unselectedLabelColor: slate400,
        indicatorColor: emerald500,
        labelStyle: TextStyle(fontWeight: FontWeight.w600, fontSize: 14),
        unselectedLabelStyle: TextStyle(fontWeight: FontWeight.w500, fontSize: 14),
      ),
      chipTheme: ChipThemeData(
        backgroundColor: slate800,
        selectedColor: emerald500.withOpacity(0.2),
        secondarySelectedColor: emerald500,
        labelStyle: const TextStyle(color: slate50, fontSize: 13),
        secondaryLabelStyle: const TextStyle(color: emerald500, fontWeight: FontWeight.w600),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(20),
          side: const BorderSide(color: slate700),
        ),
      ),
    );
  }
}
