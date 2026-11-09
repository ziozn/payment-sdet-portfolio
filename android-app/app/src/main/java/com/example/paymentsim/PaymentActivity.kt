package com.example.paymentsim

import android.app.Activity
import android.os.Bundle
import android.widget.Button
import android.widget.EditText
import android.widget.TextView
import java.math.BigDecimal

class PaymentActivity : Activity() {
    private lateinit var amountInput: EditText
    private lateinit var amountResult: TextView
    private lateinit var statusResult: TextView
    private lateinit var transactionIdResult: TextView

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_payment)

        amountInput = findViewById(R.id.et_payment_amount)
        amountResult = findViewById(R.id.tv_payment_amount_result)
        statusResult = findViewById(R.id.tv_payment_status)
        transactionIdResult = findViewById(R.id.tv_transaction_id)

        findViewById<Button>(R.id.btn_submit_payment).setOnClickListener {
            showUiDemoResult()
        }
        findViewById<Button>(R.id.btn_back_home).setOnClickListener {
            finish()
        }
    }

    private fun showUiDemoResult() {
        val enteredAmount = amountInput.text.toString().trim()
        val amount = if (Regex("[0-9]+(?:\\.[0-9]{1,2})?").matches(enteredAmount)) {
            enteredAmount.toBigDecimalOrNull()
        } else {
            null
        }
        val amountInCents = try {
            amount?.movePointRight(2)?.longValueExact()
        } catch (_: ArithmeticException) {
            null
        }

        if (amountInCents == null || amountInCents !in 1L..1_000_000L) {
            amountResult.text = getString(R.string.payment_amount_not_available)
            statusResult.text = getString(R.string.payment_invalid_amount)
            transactionIdResult.text = getString(R.string.transaction_id_not_created)
            return
        }

        val normalizedAmount = BigDecimal.valueOf(amountInCents, 2).toPlainString()
        amountResult.text = getString(R.string.payment_amount_result, normalizedAmount)
        statusResult.text = getString(R.string.payment_ui_demo_status, normalizedAmount)
        transactionIdResult.text = getString(R.string.transaction_id_not_created)
    }
}
