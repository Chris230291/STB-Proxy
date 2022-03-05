function login () {
    // (A) GET EMAIL + PASSWORD
    var data = new FormData(document.getElementById("login"));
   
    // (B) AJAX REQUEST
    fetch("/lin", { method:"POST", body:data })
    .then((res) => { return res.text(); })
    .then((txt) => {
    if (txt=="OK") { location.href = "../portals"; }
      else { alert(txt); }
    })
    .catch((err) => {
      alert("Server error - " + err.message);
      console.error(err);
    });
    return false;
  }