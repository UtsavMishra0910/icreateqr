function getCookie(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) return parts.pop().split(";").shift();
    return null;
}

document.addEventListener("DOMContentLoaded", () => {
    const flash = getCookie("flash");
    if (flash) {
        window.alert(decodeURIComponent(flash));
        document.cookie = "flash=; Max-Age=0; path=/";
    }
});
