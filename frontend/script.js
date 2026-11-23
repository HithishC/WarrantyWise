const API_BASE_URL = "http://127.0.0.1:8000";

const API_URL = `${API_BASE_URL}/assistant`;
const UPLOAD_URL = `${API_BASE_URL}/receipts/upload`;
const CONFIRM_URL = `${API_BASE_URL}/receipts/confirm`;

// Chat elements
const chatForm = document.getElementById("chatForm");
const userInput = document.getElementById("userInput");
const chatContainer = document.getElementById("chatContainer");
const sendButton = document.getElementById("sendButton");
const sendButtonText = document.getElementById("sendButtonText");

const resultSection = document.getElementById("resultSection");
const resultContent = document.getElementById("resultContent");

const newChatNav = document.getElementById("newChatNav");
const homeNav = document.getElementById("homeNav");

// Receipt upload elements
const uploadForm = document.getElementById("uploadForm");
const receiptFile = document.getElementById("receiptFile");
const selectedFileName = document.getElementById("selectedFileName");
const uploadButton = document.getElementById("uploadButton");
const uploadButtonText = document.getElementById("uploadButtonText");
const uploadStatus = document.getElementById("uploadStatus");

const receiptReview = document.getElementById("receiptReview");
const confirmForm = document.getElementById("confirmForm");
const confirmButton = document.getElementById("confirmButton");
const confirmButtonText = document.getElementById("confirmButtonText");
const cancelReviewButton = document.getElementById("cancelReviewButton");

const savedReceiptResult = document.getElementById("savedReceiptResult");

let pendingReceiptId = null;


// --------------------------------------------------
// GENERAL HELPERS
// --------------------------------------------------

function showStatus(element, message, type) {
    element.textContent = message;
    element.className = `upload-status ${type}`;
}

async function getErrorMessage(response) {
    try {
        const data = await response.json();

        if (typeof data.detail === "string") {
            return data.detail;
        }

        if (Array.isArray(data.detail)) {
            return data.detail
                .map((item) => item.msg || "Invalid input")
                .join(", ");
        }

        return data.message || "Request failed.";
    } catch {
        return "Request failed. Please try again.";
    }
}


// --------------------------------------------------
// RECEIPT UPLOAD
// --------------------------------------------------

receiptFile.addEventListener("change", function() {
    const file = receiptFile.files[0];

    selectedFileName.textContent = file
        ? file.name
        : "No file selected";
});


uploadForm.addEventListener("submit", async function(event) {
    event.preventDefault();

    const file = receiptFile.files[0];

    if (!file) {
        showStatus(
            uploadStatus,
            "Please select a receipt first.",
            "error"
        );
        return;
    }

    const allowedExtensions = ["jpg", "jpeg", "png", "pdf"];
    const extension = file.name.split(".").pop().toLowerCase();

    if (!allowedExtensions.includes(extension)) {
        showStatus(
            uploadStatus,
            "Only JPG, JPEG, PNG and PDF files are supported.",
            "error"
        );
        return;
    }

    if (file.size > 10 * 1024 * 1024) {
        showStatus(
            uploadStatus,
            "File size must be 10 MB or less.",
            "error"
        );
        return;
    }

    const formData = new FormData();
    formData.append("file", file);

    uploadButton.disabled = true;
    uploadButtonText.textContent = "Scanning receipt...";

    receiptReview.classList.add("hidden");
    savedReceiptResult.classList.add("hidden");

    showStatus(
        uploadStatus,
        "Uploading receipt. OCR and AI extraction may take a little time...",
        "info"
    );

    try {
        const response = await fetch(UPLOAD_URL, {
            method: "POST",
            body: formData
        });

        if (!response.ok) {
            throw new Error(await getErrorMessage(response));
        }

        const data = await response.json();

        pendingReceiptId = data.pending_id;

        if (!pendingReceiptId || !data.extracted) {
            throw new Error(
                "The server returned incomplete receipt information."
            );
        }

        populateReceiptReview(data.extracted);

        showStatus(
            uploadStatus,
            "Receipt scanned successfully. Review the extracted information below.",
            "success"
        );

        receiptReview.classList.remove("hidden");

        receiptReview.scrollIntoView({
            behavior: "smooth",
            block: "center"
        });

    } catch (error) {
        showStatus(
            uploadStatus,
            `Receipt upload failed: ${error.message}`,
            "error"
        );

        console.error("Receipt upload error:", error);

    } finally {
        uploadButton.disabled = false;
        uploadButtonText.textContent = "Upload and scan receipt";
    }
});


// Fill the review form with AI-extracted information.
function populateReceiptReview(data) {
    document.getElementById("reviewBrand").value =
        data.brand || "";

    document.getElementById("reviewProduct").value =
        data.product || "";

    document.getElementById("reviewDate").value =
        data.purchase_date || "";

    document.getElementById("reviewPrice").value =
        data.price ?? "";

    document.getElementById("reviewWarranty").value =
        data.warranty_years ?? "";
}


// --------------------------------------------------
// CONFIRM AND SAVE RECEIPT
// --------------------------------------------------

confirmForm.addEventListener("submit", async function(event) {
    event.preventDefault();

    if (!pendingReceiptId) {
        showStatus(
            uploadStatus,
            "No pending receipt found. Please upload the receipt again.",
            "error"
        );
        return;
    }

    const brand = document.getElementById("reviewBrand").value.trim();
    const product = document.getElementById("reviewProduct").value.trim();
    const purchaseDate = document.getElementById("reviewDate").value;

    const priceValue = document.getElementById("reviewPrice").value.trim();
    const warrantyValue = document.getElementById("reviewWarranty").value.trim();

    if (!brand || !product || !purchaseDate) {
        showStatus(
            uploadStatus,
            "Brand, product and purchase date are required.",
            "error"
        );
        return;
    }

    const price = priceValue === ""
        ? null
        : Number(priceValue);

    const warrantyYears = warrantyValue === ""
        ? null
        : Number(warrantyValue);

    if (price !== null && (!Number.isFinite(price) || price < 0)) {
        showStatus(
            uploadStatus,
            "Please enter a valid price.",
            "error"
        );
        return;
    }

    if (
        warrantyYears !== null &&
        (!Number.isInteger(warrantyYears) || warrantyYears <= 0)
    ) {
        showStatus(
            uploadStatus,
            "Warranty duration must be a positive whole number.",
            "error"
        );
        return;
    }

    const confirmationData = {
        pending_id: pendingReceiptId,
        brand: brand,
        product: product,
        purchase_date: purchaseDate,
        price: price,
        warranty_years: warrantyYears
    };

    confirmButton.disabled = true;
    confirmButtonText.textContent = "Saving receipt...";

    try {
        const response = await fetch(CONFIRM_URL, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify(confirmationData)
        });

        if (!response.ok) {
            throw new Error(await getErrorMessage(response));
        }

        const data = await response.json();

        displaySavedReceipt(data);

        pendingReceiptId = null;

        receiptReview.classList.add("hidden");

        uploadForm.reset();
        selectedFileName.textContent = "No file selected";

        showStatus(
            uploadStatus,
            "Receipt confirmed and saved successfully!",
            "success"
        );

        savedReceiptResult.scrollIntoView({
            behavior: "smooth",
            block: "center"
        });

    } catch (error) {
        showStatus(
            uploadStatus,
            `Could not save receipt: ${error.message}`,
            "error"
        );

        console.error("Receipt confirmation error:", error);

    } finally {
        confirmButton.disabled = false;
        confirmButtonText.textContent = "Confirm and save receipt";
    }
});


// Display the saved receipt and warranty status.
function displaySavedReceipt(data) {
    savedReceiptResult.replaceChildren();

    const receipt = data.receipt;
    const warranty = data.warranty;

    const heading = document.createElement("div");
    heading.className = "receipt-saved-title";
    heading.textContent = "✓ Receipt saved successfully";

    const product = document.createElement("p");

    const productLabel = document.createElement("strong");
    productLabel.textContent = "Product: ";

    product.appendChild(productLabel);
    product.appendChild(
        document.createTextNode(`${receipt.brand} ${receipt.product}`)
    );

    const receiptId = document.createElement("p");
    const receiptLabel = document.createElement("strong");
    receiptLabel.textContent = "Receipt ID: ";

    receiptId.appendChild(receiptLabel);
    receiptId.appendChild(
        document.createTextNode(receipt.receipt_id)
    );

    const purchaseDate = document.createElement("p");
    purchaseDate.textContent =
        `Purchase date: ${receipt.purchase_date}`;

    const expiry = document.createElement("p");
    expiry.textContent = warranty.expiry_date
        ? `Warranty expiry: ${warranty.expiry_date}`
        : "Warranty expiry: Cannot verify";

    const status = document.createElement("span");
    status.className = "saved-status";
    status.textContent = warranty.status;

    savedReceiptResult.appendChild(heading);
    savedReceiptResult.appendChild(product);
    savedReceiptResult.appendChild(receiptId);
    savedReceiptResult.appendChild(purchaseDate);
    savedReceiptResult.appendChild(expiry);
    savedReceiptResult.appendChild(status);

    savedReceiptResult.classList.remove("hidden");
}


// Cancel the pending review.
cancelReviewButton.addEventListener("click", function() {
    pendingReceiptId = null;

    receiptReview.classList.add("hidden");
    savedReceiptResult.classList.add("hidden");

    receiptFile.value = "";
    selectedFileName.textContent = "No file selected";

    showStatus(
        uploadStatus,
        "Receipt review cancelled. You can upload another receipt.",
        "info"
    );
});

// --------------------------------------------------
// CHAT MESSAGES
// --------------------------------------------------

function addMessage(message, sender) {
    const messageElement = document.createElement("div");
    messageElement.className = `chat-message ${sender}-message`;

    if (sender === "assistant") {
        const avatar = document.createElement("div");
        avatar.className = "message-avatar";
        avatar.textContent = "W";
        messageElement.appendChild(avatar);
    }

    const content = document.createElement("div");
    content.className = "message-content";

    const author = document.createElement("div");
    author.className = "message-author";
    author.textContent = sender === "assistant"
        ? "WarrantyWise AI Assistant"
        : "You";

    const bubble = document.createElement("div");
    bubble.className = "message-bubble";
    bubble.textContent = message;

    content.appendChild(author);
    content.appendChild(bubble);
    messageElement.appendChild(content);

    chatContainer.appendChild(messageElement);
    chatContainer.scrollTop = chatContainer.scrollHeight;
}


// --------------------------------------------------
// CHAT LOADING MESSAGE
// --------------------------------------------------

function showLoading() {
    const loading = document.createElement("div");
    loading.className = "chat-message assistant-message";
    loading.id = "loadingMessage";

    const avatar = document.createElement("div");
    avatar.className = "message-avatar";
    avatar.textContent = "W";

    const content = document.createElement("div");
    content.className = "message-content";

    const author = document.createElement("div");
    author.className = "message-author";
    author.textContent = "WarrantyWise";

    const bubble = document.createElement("div");
    bubble.className = "message-bubble";
    bubble.textContent =
        "Checking your purchase records and warranty...";

    content.appendChild(author);
    content.appendChild(bubble);

    loading.appendChild(avatar);
    loading.appendChild(content);

    chatContainer.appendChild(loading);
    chatContainer.scrollTop = chatContainer.scrollHeight;
}


function hideLoading() {
    const loading = document.getElementById("loadingMessage");

    if (loading) {
        loading.remove();
    }
}


// --------------------------------------------------
// WARRANTY REPORT HELPERS
// --------------------------------------------------

function createInfoItem(label, value) {
    const item = document.createElement("div");
    item.className = "info-item";

    const heading = document.createElement("small");
    heading.textContent = label;

    const content = document.createElement("strong");
    content.textContent =
        value === null || value === undefined || value === ""
            ? "Not available"
            : value;

    item.appendChild(heading);
    item.appendChild(content);

    return item;
}


function updateReportBadge(found) {
    const badge = document.querySelector(".verified-label");

    if (!badge) return;

    if (found) {
        badge.textContent = "✓ VERIFIED RESULT";
        badge.style.color = "#35d69a";
        badge.style.background = "#35d69a18";
    } else {
        badge.textContent = "⚠ NOT VERIFIED";
        badge.style.color = "#ffc46b";
        badge.style.background = "#ffc46b18";
    }
}


// --------------------------------------------------
// NOT FOUND REPORT
// --------------------------------------------------

function displayNotFoundReport(data) {
    updateReportBadge(false);

    const report = data.report;

    const card = document.createElement("div");
    card.className = "result-card";

    const heading = document.createElement("h4");
    heading.textContent = "Purchase Record Not Found";

    const grid = document.createElement("div");
    grid.className = "result-grid";

    grid.appendChild(
        createInfoItem("SEARCHED PRODUCT", report.searched_for)
    );

    grid.appendChild(
        createInfoItem("RECEIPT STATUS", report.receipt_status)
    );

    grid.appendChild(
        createInfoItem("WARRANTY STATUS", report.warranty_status)
    );

    grid.appendChild(
        createInfoItem("CLAIM STATUS", report.claim_status)
    );

    const status = document.createElement("span");
    status.className = "warranty-status unknown";
    status.textContent = "⚠ Warranty Not Verified";

    const nextSteps = document.createElement("div");
    nextSteps.className = "claim-notice";

    const nextHeading = document.createElement("strong");
    nextHeading.textContent = "What you can do next";

    nextSteps.appendChild(nextHeading);

    const list = document.createElement("ul");
    list.style.paddingLeft = "20px";
    list.style.marginTop = "10px";

    (report.next_steps || []).forEach((step) => {
        const item = document.createElement("li");
        item.textContent = step;
        item.style.marginBottom = "7px";
        list.appendChild(item);
    });

    nextSteps.appendChild(list);

    const disclaimer = document.createElement("p");
    disclaimer.className = "claim-description";
    disclaimer.style.marginTop = "15px";
    disclaimer.textContent =
        "No warranty details have been assumed or fabricated. " +
        "A purchase record is required to verify coverage.";

    card.appendChild(heading);
    card.appendChild(grid);
    card.appendChild(status);
    card.appendChild(nextSteps);
    card.appendChild(disclaimer);

    resultContent.appendChild(card);
}


// --------------------------------------------------
// MATCHING PRODUCT REPORT
// --------------------------------------------------

function displayFoundReport(data) {
    const product = data.product;

    if (!product) {
        updateReportBadge(false);
        return;
    }

    // A verified expiry is still a verified warranty result.
    // Missing or unknown warranty information must not be marked verified.
    updateReportBadge(
        product.status === "Under Warranty" ||
        product.status === "Warranty Expired"
    );

    const productCard = document.createElement("div");
    productCard.className = "result-card";

    const productName = document.createElement("div");
    productName.className = "product-name";

    const brand = product.brand || "";
    const productText = product.product || "";

    productName.textContent =
        productText.toLowerCase().startsWith(brand.toLowerCase())
            ? productText
            : `${brand} ${productText}`.trim();

    const receipt = document.createElement("p");
    receipt.className = "receipt-id";
    receipt.textContent = `Receipt ID: ${product.receipt_id}`;

    const grid = document.createElement("div");
    grid.className = "result-grid";

    grid.appendChild(
        createInfoItem("PURCHASE DATE", product.purchase_date)
    );

    grid.appendChild(
        createInfoItem("WARRANTY EXPIRY", product.expiry_date)
    );

    productCard.appendChild(productName);
    productCard.appendChild(receipt);
    productCard.appendChild(grid);

    const status = document.createElement("span");

    if (product.status === "Under Warranty") {
        status.className = "warranty-status valid";
        status.textContent = "✓ Under Warranty";
    } else if (product.status === "Warranty Expired") {
        status.className = "warranty-status expired";
        status.textContent = "✕ Warranty Expired";
    } else {
        status.className = "warranty-status unknown";
        status.textContent = "⚠ Warranty Cannot Be Verified";
    }

    productCard.appendChild(status);
    resultContent.appendChild(productCard);

    // Display claim draft, if available.
    if (data.claim) {
        const claimCard = document.createElement("div");
        claimCard.className = "result-card claim-card";

        const heading = document.createElement("h4");
        heading.textContent = "Warranty Claim Draft";

        const claimStatus = document.createElement("p");
        claimStatus.className = "claim-status";
        claimStatus.textContent =
            `✓ ${data.claim.claim_status}`;

        const description = document.createElement("p");
        description.className = "claim-description";
        description.textContent =
            `Issue: ${data.claim.issue_description}`;

        const notice = document.createElement("div");
        notice.className = "claim-notice";
        notice.textContent =
            "Approval required: Please review this draft. " +
            "It has not been submitted to the manufacturer.";

        claimCard.appendChild(heading);
        claimCard.appendChild(claimStatus);
        claimCard.appendChild(description);
        claimCard.appendChild(notice);

        resultContent.appendChild(claimCard);
    }
}

// --------------------------------------------------
// DISPLAY COMPLETE REPORT
// --------------------------------------------------

function displayResult(data, originalMessage) {
    resultContent.replaceChildren();
    resultSection.classList.remove("hidden");

    if (data.multiple_matches) {
        updateReportBadge(false);

        const heading = document.createElement("h4");
        heading.textContent = "Select a matching product";

        const description = document.createElement("p");
        description.textContent =
            "We found multiple purchase records. Choose the correct receipt to continue.";

        resultContent.appendChild(heading);
        resultContent.appendChild(description);

        (data.matches || []).forEach((product) => {
            const button = document.createElement("button");
            button.className = "match-button";

            // Show enough receipt information to help the user
            // distinguish similar products before selecting one.
            const brand = product.brand || "";
            const productName = product.product || "Unknown product";

            const fullName = productName.toLowerCase().startsWith(brand.toLowerCase())
                ? productName
                : `${brand} ${productName}`.trim();

            const warrantyYears = product.warranty_years;

            const warrantyDescription =
                warrantyYears === null ||
                warrantyYears === undefined ||
                warrantyYears === ""
                    ? "⚠ Cannot verify — warranty duration not recorded"
                    : `Warranty duration recorded: ${warrantyYears} ${
                        Number(warrantyYears) === 1 ? "year" : "years"
                    }`;

            button.textContent =
                `${fullName}\n` +
                `Receipt ID: ${product.receipt_id || "Not available"}\n` +
                `Purchase date: ${product.purchase_date || "Not available"}\n` +
                warrantyDescription;

            button.style.whiteSpace = "pre-line";
            button.style.textAlign = "left";
            button.style.lineHeight = "1.6";

            button.setAttribute(
                "aria-label",
                `${fullName}. Receipt ID: ${product.receipt_id || "Not available"}. ` +
                `Purchase date: ${product.purchase_date || "Not available"}. ` +
                warrantyDescription
            );

            button.addEventListener("click", () => {
                // Send the original request with the exact selected ID.
                // Do not add a duplicate user message.
                sendMessage(
                    originalMessage,
                    product.receipt_id,
                    false
                );
            });

            resultContent.appendChild(button);
        });

        return;
    }

    if (data.found === false) {
        displayNotFoundReport(data);
        return;
    }

    if (!data.success) {
        updateReportBadge(false);

        const error = document.createElement("div");
        error.className = "error-message";
        error.textContent = data.message || "Something went wrong.";

        resultContent.appendChild(error);
        return;
    }

    displayFoundReport(data);
}


// --------------------------------------------------
// SEND CHAT MESSAGE TO FASTAPI
// --------------------------------------------------

async function sendMessage(
    message,
    receiptId = null,
    displayUserMessage = true
) {
    if (!message.trim()) return;

    if (displayUserMessage) {
        addMessage(message, "user");
    }

    userInput.value = "";
    sendButton.disabled = true;
    sendButtonText.textContent = "Checking...";

    showLoading();

    try {
        const requestBody = {
            message: message
        };

        // Include receipt_id only when a user selects a receipt.
        if (receiptId) {
            requestBody.receipt_id = receiptId;
        }

        const response = await fetch(API_URL, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify(requestBody)
        });

        if (!response.ok) {
            throw new Error(await getErrorMessage(response));
        }

        const data = await response.json();

        hideLoading();

        addMessage(data.message, "assistant");
        displayResult(data, message);

        resultSection.scrollIntoView({
            behavior: "smooth",
            block: "start"
        });

    } catch (error) {
        hideLoading();

        addMessage(
            `Unable to connect to WarrantyWise. ${error.message}`,
            "assistant"
        );

        console.error("WarrantyWise error:", error);

    } finally {
        sendButton.disabled = false;
        sendButtonText.textContent = "Send message";
        userInput.focus();
    }
}


// Chat form
chatForm.addEventListener("submit", function(event) {
    event.preventDefault();

    const message = userInput.value.trim();

    if (message) {
        sendMessage(message);
    }
});


// Quick actions
const actionCards = document.querySelectorAll("[data-prompt]");

actionCards.forEach((card) => {
    card.addEventListener("click", function() {
        sendMessage(card.getAttribute("data-prompt"));
    });
});


// New conversation
newChatNav.addEventListener("click", function() {
    chatContainer.replaceChildren();
    resultContent.replaceChildren();

    resultSection.classList.add("hidden");
    updateReportBadge(true);

    addMessage(
        "Hello! I'm your WarrantyWise assistant. " +
        "What product would you like me to check?",
        "assistant"
    );

    userInput.value = "";
    userInput.focus();
});


// Dashboard navigation
homeNav.addEventListener("click", function() {
    window.scrollTo({
        top: 0,
        behavior: "smooth"
    });
});


// Enter to send, Shift + Enter for a new line
userInput.addEventListener("keydown", function(event) {
    if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        chatForm.requestSubmit();
    }
});