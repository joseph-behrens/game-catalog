function validateForm() {
    var image_text = document.getElementById('image_text');
    var image_url = document.getElementById('image_url');
    if (image_text.value.trim() == '' && image_url.value.trim() != '') {
        image_text_error.innerHTML = 'An image name is required to add an image';
        return false;
    }
    if (image_text.value.trim() != '' && image_url.value.trim() == '') {
        image_url_error.innerHTML = 'A url is required to add an image';
        return false;
    }
}

function showNewImageFields() {
    document.getElementById('image_drop_down').style.display = "none";
    document.getElementById('new_image_text').style.display = "block";
    document.getElementById('new_image_url').style.display = "block";
}

function hideNewImageFields() {
    document.getElementById('image_drop_down').style.display = "block";
    document.getElementById('new_image_text').style.display = "none";
    document.getElementById('new_image_url').style.display = "none";
}