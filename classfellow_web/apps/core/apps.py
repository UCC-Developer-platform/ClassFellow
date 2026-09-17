from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.core"
    verbose_name = "Core Framework"

    def ready(self):
        # SQLite Decimal Converter Guard:
        # Handles Decimal and string values returned from SQLite when global Decimal adapters are active
        try:
            import decimal
            from django.db.backends.sqlite3.operations import DatabaseOperations
            from django.db.models.expressions import Col

            def safe_get_decimalfield_converter(self, expression):
                if isinstance(expression, Col):
                    quantize_value = decimal.Decimal(1).scaleb(
                        -expression.output_field.decimal_places
                    )

                    def converter(value, expression, connection):
                        if value is not None:
                            if isinstance(value, decimal.Decimal):
                                return value.quantize(quantize_value, context=expression.output_field.context)
                            if isinstance(value, str):
                                return decimal.Decimal(value).quantize(quantize_value, context=expression.output_field.context)
                            return decimal.Context(prec=15).create_decimal_from_float(value).quantize(
                                quantize_value, context=expression.output_field.context
                            )

                    return converter
                else:
                    def converter(value, expression, connection):
                        if value is not None:
                            if isinstance(value, (decimal.Decimal, str)):
                                return decimal.Decimal(value)
                            return decimal.Context(prec=15).create_decimal_from_float(value)

                    return converter

            DatabaseOperations.get_decimalfield_converter = safe_get_decimalfield_converter
        except Exception:
            pass


