function logout() {
    // (B) AJAX REQUEST
    fetch("/lout", { method:"POST" })
    .then((res) => { return res.text(); })
    .then((txt) => {
    if (txt=="OK") { location.href = "../login"; }
      else { alert(txt); }
    })
    .catch((err) => {
      alert("Server error - " + err.message);
      console.error(err);
    });
    return false;
  }