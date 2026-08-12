let isSpinning = false;
let isAutoPlaying = false;
let autoTimer = null;
let freeSpinsLeft = 0;

// Danh sách các file ảnh quân cờ trong thư mục static/assets/
const tileList = [
    { file: "Man1.png", name: "Man1" }, { file: "Man2.png", name: "Man2" }, 
    { file: "Man3.png", name: "Man3" }, { file: "Man4.png", name: "Man4" },
    { file: "Man5.png", name: "Man5" }, { file: "Man6.png", name: "Man6" },
    { file: "Man7.png", name: "Man7" }, { file: "Man8.png", name: "Man8" },
    { file: "Pin1.png", name: "Pin1" }, { file: "Pin2.png", name: "Pin2" }, 
    { file: "Pin3.png", name: "Pin3" }, { file: "Pin4.png", name: "Pin4" },
    { file: "Pin5.png", name: "Pin5" }, { file: "Pin6.png", name: "Pin6" },
    { file: "Pin7.png", name: "Pin7" }, { file: "Sou1.png", name: "Sou1" },
    { file: "Sou2.png", name: "Sou2" }, { file: "Sou3.png", name: "Sou3" }, 
    { file: "Sou4.png", name: "Sou4" }
];
const scatterData = { file: "scatter.png", name: "scatter" };

const rows = 6; // Đã đổi lên 6 hàng
const cols = 5;
let currentMultiplierIndex = 0; 
const multipliers = [1, 2, 3, 5];

function updateMultiplierDisplay() {
    document.querySelectorAll('.mult-item').forEach((el, idx) => {
        if (idx === currentMultiplierIndex) {
            el.classList.add('active');
        } else {
            el.classList.remove('active');
        }
    });
}

function startSpin() {
    if (isSpinning) return;

    const betMultiplier = parseFloat(document.getElementById('bet-amount').value);
    const betInput = betMultiplier * 5000; 

    if (freeSpinsLeft > 0) {
        freeSpinsLeft--;
        document.getElementById('freespin-badge').innerText = `MIỄN PHÍ: ${freeSpinsLeft}`;
        if (freeSpinsLeft === 0) {
            document.getElementById('freespin-badge').style.display = 'none';
        }
    } else {
        if (balance < betInput) {
            alert("Số dư tài khoản không đủ để đặt cược!");
            stopAutoPlay();
            return;
        }
        balance -= betInput;
        updateBalance();
    }

    isSpinning = true;
    document.getElementById('win-text').innerText = "";
    
    const spinBtn = document.getElementById('spin-btn');
    spinBtn.disabled = true;
    spinBtn.classList.add('rotating');
    
    currentMultiplierIndex = 0;
    updateMultiplierDisplay();

    let willTriggerFreeSpins = (Math.random() < 0.25 || freeSpinsLeft > 0);
    let finalGridData = [];

    for (let c = 0; c < cols; c++) {
        let colTiles = [];
        for (let r = 0; r < rows; r++) {
            let chosen = tileList[Math.floor(Math.random() * tileList.length)];
            if (willTriggerFreeSpins && c < 3 && r === 0 && Math.random() < 0.8) {
                chosen = scatterData;
            }
            colTiles.push(chosen);
        }
        finalGridData.push(colTiles);
    }

    for (let c = 0; c < cols; c++) {
        const track = document.getElementById(`reel-track-${c}`);
        let htmlContent = '';
        // Tạo các ô trượt hiệu ứng phía trên
        for (let i = 0; i < 8; i++) {
            let randT = tileList[Math.floor(Math.random() * tileList.length)];
            htmlContent += `<div class="reel-cell"><img src="/static/assets/${randT.file}" alt="tile"></div>`;
        }
        // Tạo các ô kết quả chính thức cho 6 hàng
        for (let r = 0; r < rows; r++) {
            let finalT = finalGridData[c][r];
            let isGold = Math.random() < 0.2 ? 'gold-border' : '';
            let isScatter = finalT.file === scatterData.file ? 'scatter-glow' : '';
            htmlContent += `<div class="reel-cell ${isGold} ${isScatter}" data-name="${finalT.name}"><img src="/static/assets/${finalT.file}" alt="tile"></div>`;
        }
        track.innerHTML = htmlContent;
        track.style.transition = 'none';
        track.style.transform = 'translate3d(0, 0px, 0)';
    }

    requestAnimationFrame(() => {
        requestAnimationFrame(() => {
            for (let c = 0; c < cols; c++) {
                const track = document.getElementById(`reel-track-${c}`);
                track.style.transition = 'transform 0.7s cubic-bezier(0.25, 1, 0.5, 1)';
                let targetY = -8 * 45; // Khoảng cách trượt cho 8 hàng ẩn
                track.style.transform = `translate3d(0, ${targetY}px, 0)`;
            }
        });
    });

    setTimeout(() => {
        finishSpinProcess(spinBtn, betInput);
    }, 750);
}

async function finishSpinProcess(spinBtn, betInput) {
    let totalScatters = 0;
    const cells = document.querySelectorAll('.reel-cell');
    cells.forEach(cell => {
        if (cell.dataset.name === "scatter") totalScatters++;
    });

    if (totalScatters >= 3 && freeSpinsLeft === 0) {
        freeSpinsLeft = 10;
        const badge = document.getElementById('freespin-badge');
        badge.style.display = 'block';
        badge.innerText = `MIỄN PHÍ: ${freeSpinsLeft}`;
        
        await showWinPopup("FREESPIN", "10 LƯỢT QUAY MIỄN PHÍ");
    }

    await evaluateWin(betInput);

    isSpinning = false;
    spinBtn.disabled = false;
    spinBtn.classList.remove('rotating');

    if (isAutoPlaying || freeSpinsLeft > 0) {
        autoTimer = setTimeout(() => {
            if (isAutoPlaying || freeSpinsLeft > 0) startSpin();
        }, 700);
    }
}

function toggleAutoPlay() {
    const autoBtn = document.getElementById('auto-btn');
    isAutoPlaying = !isAutoPlaying;

    if (isAutoPlaying) {
        autoBtn.classList.add('active');
        autoBtn.innerText = 'DỪNG';
        if (!isSpinning) startSpin();
    } else {
        stopAutoPlay();
    }
}

function stopAutoPlay() {
    isAutoPlaying = false;
    clearTimeout(autoTimer);
    const autoBtn = document.getElementById('auto-btn');
    autoBtn.classList.remove('active');
    autoBtn.innerText = 'AUTO';
}

async function evaluateWin(betInput) {
    let matchedSymbols = {};
    for (let c = 0; c < cols; c++) {
        const track = document.getElementById(`reel-track-${c}`);
        const allCellsInTrack = track.querySelectorAll('.reel-cell');
        for (let i = allCellsInTrack.length - rows; i < allCellsInTrack.length; i++) {
            if(allCellsInTrack[i]) {
                let name = allCellsInTrack[i].dataset.name;
                if(name) matchedSymbols[name] = (matchedSymbols[name] || 0) + 1;
            }
        }
    }

    let totalWin = 0;
    let hasWon = false;

    for (let name in matchedSymbols) {
        if (matchedSymbols[name] >= 4) {
            hasWon = true;
            let baseMultiplier = matchedSymbols[name] * 0.35;
            totalWin += betInput * baseMultiplier;
        }
    }

    let luckFactor = (freeSpinsLeft > 0) ? 2 : 1;

    if (hasWon || luckFactor > 1 && totalWin > 0) {
        let multValue = multipliers[currentMultiplierIndex];
        totalWin = Math.floor(totalWin * multValue * luckFactor);
        balance += totalWin;

        let freeText = freeSpinsLeft > 0 ? " (FREE SPIN x2)" : "";
        document.getElementById('win-text').innerHTML = `🎉 THẮNG${freeText}: +${totalWin.toLocaleString()} VNĐ!`;

        if (totalWin >= betInput * 12) {
            await showWinPopup("BIG WIN", `+${totalWin.toLocaleString()} VNĐ`);
        }
        
        if (currentMultiplierIndex < multipliers.length - 1) {
            currentMultiplierIndex++;
        }
        updateMultiplierDisplay();
    } else if (totalWin === 0 && freeSpinsLeft === 0) {
        document.getElementById('win-text').innerHTML = `Chúc bạn may mắn lần sau!`;
    }

    updateBalance();
}

function showWinPopup(title, desc) {
    return new Promise((resolve) => {
        const overlay = document.getElementById('win-overlay');
        const popupBox = document.getElementById('popup-content-box');
        popupBox.innerHTML = `<div class="win-popup-title">${title}</div><div class="win-popup-desc">${desc}</div>`;
        overlay.classList.add('show');
        setTimeout(() => {
            closeWinPopupEarly();
            resolve();
        }, 2000);
    });
}

function closeWinPopupEarly() {
    document.getElementById('win-overlay').classList.remove('show');
}

function updateBalance() {
    document.getElementById('balance').innerText = balance.toLocaleString('vi-VN');
}
